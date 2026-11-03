from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from betclic_bot.config import Settings
from betclic_bot.odds_api import QuotaExhausted, QuotaInfo
from betclic_bot.quota import QuotaManager
from betclic_bot.scanner import Scanner

from conftest import make_team


class TestQuota:
    def test_budget_spreads_credits_over_month(self, tmp_path, now):
        q = QuotaManager(tmp_path / "q.json", monthly_credits=500, reserve=30, runs_per_day=2)
        # 470 crédits / (29 jours × 2 runs) ≈ 8.1 crédits → 4 compétitions à 2 crédits (h2h + totals)
        assert q.sports_budget(now) == 4
        # Pipeline quotidien : 1 seul run par jour → 8 compétitions
        daily = QuotaManager(tmp_path / "d.json", monthly_credits=500, reserve=30, runs_per_day=1)
        assert daily.sports_budget(now) == 8

    def test_budget_uses_api_header(self, tmp_path, now):
        q = QuotaManager(tmp_path / "q.json", reserve=30)
        q.update_from_api(QuotaInfo(remaining=35), now)
        assert q.sports_budget(now) == 1
        q.update_from_api(QuotaInfo(remaining=30), now)
        assert q.sports_budget(now) == 0

    def test_month_rollover_resets_usage(self, tmp_path, now):
        q = QuotaManager(tmp_path / "q.json")
        q.record_call("soccer_epl", QuotaInfo(remaining=10, last_cost=3), now)
        assert q.remaining(now) == 10
        q.save()
        q2 = QuotaManager(tmp_path / "q.json")
        assert q2.remaining(now + timedelta(days=30)) == 500

    def test_rank_rotation(self, tmp_path, now):
        q = QuotaManager(tmp_path / "q.json")
        weights = {"basketball_nba": 3.0, "soccer_epl": 3.0, "soccer_sweden_allsvenskan": 0.5}
        q.mark_scanned("basketball_nba", now - timedelta(hours=1))
        assert q.rank(weights, now) == ["soccer_epl", "soccer_sweden_allsvenskan", "basketball_nba"]


class FakeClient:
    def __init__(self, event, exhaust_after=None):
        self.event = event
        self.odds_calls = []
        self.exhaust_after = exhaust_after

    def get_sports(self):
        return [
            {"key": "soccer_epl", "group": "Soccer", "title": "EPL", "active": True, "has_outrights": False},
            {"key": "basketball_nba", "group": "Basketball", "title": "NBA", "active": True, "has_outrights": False},
            {"key": "golf_masters", "group": "Golf", "title": "Masters", "active": True, "has_outrights": True},
        ], QuotaInfo(remaining=400)

    def get_events(self, sport_key, start, end):
        return ([{"id": "x"}] if sport_key == "soccer_epl" else []), QuotaInfo()

    def get_odds(self, sport_key, start, end):
        if self.exhaust_after is not None and len(self.odds_calls) >= self.exhaust_after:
            raise QuotaExhausted("plus de crédits")
        self.odds_calls.append(sport_key)
        return [self.event], QuotaInfo(remaining=399, used=101, last_cost=1)


class FakeStats:
    """Stats ESPN simulées : Arsenal dominateur, Chelsea en crise."""

    def __init__(self):
        self.calls = []

    def supports(self, sport_key):
        return sport_key == "soccer_epl"

    def match_stats(self, sport_key, home, away):
        self.calls.append((home, away))
        return (make_team("Arsenal", [(3, 1), (2, 0), (3, 1), (2, 1), (4, 0)]),
                make_team("Chelsea", [(1, 2), (0, 1), (1, 1), (2, 3), (1, 2)], rank=15))


def _settings(tmp_path: Path) -> Settings:
    return Settings(odds_api_key="k", telegram_token="", telegram_chat_id="", vault_path=tmp_path,
                    state_path=tmp_path / "q.json", stats_cache_path=tmp_path / "cache",
                    ledger_path=tmp_path / "ledger.json", site_url="https://x.github.io/fonds/",
                    bankroll_override=None, default_bankroll=1000,
                    monthly_credits=500, credit_reserve=30, runs_per_day=2, max_sports_per_run=6,
                    lookahead_hours=48, devig_method="multiplicative", timezone="Europe/Paris")


def _scanner(tmp_path, client, stats_client=None):
    s = _settings(tmp_path)
    return Scanner(s, client, QuotaManager(s.state_path), stats_client if stats_client is not None else FakeStats())


def test_scan_end_to_end(tmp_path, soccer_event, now):
    client = FakeClient(soccer_event)
    stats = FakeStats()
    report = _scanner(tmp_path, client, stats).run(now=now, bankroll=10.0)

    assert client.odds_calls == ["soccer_epl"]  # NBA sans match → aucun crédit dépensé
    assert report.credits_used == 1
    assert report.bankroll == 10.0
    assert stats.calls == [("Arsenal", "Chelsea")]
    markets = {o.market for o in report.candidates}
    assert {"h2h", "totals"} <= markets and markets & {"btts", "double_chance", "dnb", "team_totals"}
    assert report.stats.derived > 0
    assert len(report.bets) == 1  # une seule issue par match
    assert report.combo_legs and all(l.convergence >= 0.6 for l in report.combo_legs)
    assert not (tmp_path / "02 - Paris Détectés").exists()  # le scanner n'écrit rien : c'est fund.py


def test_scan_without_stats_still_returns_picks(tmp_path, soccer_event, now):
    """Sans stats, le Safe est impossible mais le Sweet Spot (Over 2.5) reste proposé."""
    class NoStats(FakeStats):
        def match_stats(self, sport_key, home, away):
            return None, None

    report = _scanner(tmp_path, FakeClient(soccer_event), NoStats()).run(now=now)
    assert [(o.selection, o.profile) for o in report.bets] == [("Plus de 2.5", "SWEET_SPOT")]
    assert report.combo_legs == []  # stats obligatoires pour le combiné


def test_quota_exhausted_stops_scan(tmp_path, soccer_event, now):
    report = _scanner(tmp_path, FakeClient(soccer_event, exhaust_after=0)).run(now=now)
    assert report.stop_reason and "crédits" in report.stop_reason
    assert report.sports_scanned == []


def test_scan_report_prints_diagnostic(tmp_path, soccer_event, now, capsys):
    from betclic_bot.__main__ import _print_diagnostic

    report = _scanner(tmp_path, FakeClient(soccer_event)).run(now=now)
    _print_diagnostic(report.stats)
    out = capsys.readouterr().out
    assert "Matchs avec Pinnacle + Betclic : 1/1" in out
    assert "Lignes comparées : h2h 1 · totals 1\n" in out
    assert "Issues dérivées (modèle de Poisson) :" in out
    assert "Issues éligibles par profil : SAFE " in out
    assert "Équipes trouvées chez ESPN : 2/2" in out


@pytest.mark.parametrize("sport, markets, cost", [
    ("soccer_epl", "h2h,totals", 2),            # totals Pinnacle pour calibrer le modèle de Poisson
    ("tennis_atp_paris_masters", "h2h", 1),
])
def test_odds_request_markets(now, sport, markets, cost):
    """CLAUDE.md §1 : h2h partout, + totals en football (Betclic n'a que h2h via l'API)."""
    from betclic_bot import rules
    from betclic_bot.odds_api import OddsApiClient

    class Resp:
        status_code = 200
        headers = {"x-requests-remaining": "490", "x-requests-last": str(cost)}

        def json(self):
            return []

    class Session:
        def get(self, url, params, timeout):
            self.url, self.params = url, params
            return Resp()

    session = Session()
    _, info = OddsApiClient("k", session=session).get_odds(sport, now, now + timedelta(hours=48))
    assert session.url.endswith(f"/sports/{sport}/odds")
    assert session.params["markets"] == markets
    assert session.params["bookmakers"] == "pinnacle,betclic_fr"
    assert session.params["regions"] == "eu"
    assert rules.COST_PER_ODDS_CALL == 2  # budget calculé sur le cas le plus cher
    assert info.last_cost == cost


def test_rotation_only_espn_covered_competitions():
    from betclic_bot.sports import eligible_sports

    sports = [{"key": k, "group": g, "title": k, "active": True, "has_outrights": False} for k, g in [
        ("soccer_epl", "Soccer"), ("soccer_uefa_champs_league", "Soccer"), ("tennis_atp_paris_masters", "Tennis"),
        ("soccer_efl_champ", "Soccer"), ("soccer_brazil_campeonato", "Soccer"), ("icehockey_ahl", "Ice Hockey"),
        ("basketball_nba", "Basketball"),
    ]]
    # Tennis exclu : ni stats ni scores ESPN pour le règlement automatique
    assert set(eligible_sports(sports)) == {"soccer_epl", "soccer_uefa_champs_league", "basketball_nba"}


class TestCoverage:
    def test_moving_average(self, tmp_path):
        q = QuotaManager(tmp_path / "q.json")
        assert q.coverage("basketball_nba") is None
        assert q.coverage_factor("basketball_nba") == 1.0
        q.record_coverage("basketball_nba", 15, 0)
        assert q.coverage("basketball_nba") == 0.0
        assert q.coverage_factor("basketball_nba") == 0.1  # plancher : retesté de temps en temps
        q.record_coverage("basketball_nba", 10, 10)
        assert q.coverage("basketball_nba") == 0.5
        q.record_coverage("basketball_nba", 0, 0)  # aucun match : pas d'observation
        assert q.coverage("basketball_nba") == 0.5

    def test_uncovered_sport_is_deprioritised_but_not_dropped(self, tmp_path, now):
        q = QuotaManager(tmp_path / "q.json")
        q.record_coverage("basketball_nba", 15, 0)
        q.record_coverage("soccer_uefa_champs_league", 11, 11)
        weights = {"basketball_nba": 3.0, "soccer_uefa_champs_league": 3.0, "soccer_sweden_allsvenskan": 0.5}
        assert q.rank(weights, now)[-1] == "basketball_nba"
        # Après un long délai sans scan, la NBA repasse devant un petit championnat scanné récemment.
        q.mark_scanned("soccer_sweden_allsvenskan", now - timedelta(hours=10))
        q.mark_scanned("soccer_uefa_champs_league", now - timedelta(hours=1))
        assert q.rank(weights, now)[0] == "basketball_nba"

    def test_coverage_persisted(self, tmp_path):
        q = QuotaManager(tmp_path / "q.json")
        q.record_coverage("soccer_epl", 10, 8)
        q.save()
        assert QuotaManager(tmp_path / "q.json").coverage("soccer_epl") == 0.8


def test_scan_records_coverage(tmp_path, soccer_event, now):
    client = FakeClient(soccer_event)
    scanner = _scanner(tmp_path, client)
    report = scanner.run(now=now)
    assert report.coverage == {"soccer_epl": (1, 1)}
    assert scanner.quota.coverage("soccer_epl") == 1.0
    assert scanner.quota.coverage("basketball_nba") is None  # pas de match → pas scanné, pas d'observation


def test_coverage_requires_both_bookmakers(tmp_path, soccer_event, now):
    """NHL constatée le 02/11/2026 : Betclic présent, Pinnacle absent → match non comparable."""
    soccer_event["bookmakers"] = [b for b in soccer_event["bookmakers"] if b["key"] == "betclic_fr"]
    scanner = _scanner(tmp_path, FakeClient(soccer_event))
    report = scanner.run(now=now)
    assert report.coverage == {"soccer_epl": (0, 1)}
    assert scanner.quota.coverage("soccer_epl") == 0.0
