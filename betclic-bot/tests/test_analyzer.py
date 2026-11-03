from dataclasses import replace
from datetime import timedelta

import pytest

from betclic_bot import rules
from betclic_bot.analyzer import (REJECT_EV, REJECT_LOW_EV_STATS, REJECT_ODD, REJECT_SAFE_NO_STATS,
                                  REJECT_SAFE_PROB, REJECT_STATS,
                                  analyze, classify_profile, rejection_reason, select_top, stats_convergence,
                                  team_rating)
from betclic_bot.detector import ComparedOutcome, DetectionStats, compare_event

from conftest import NOW, make_team


def outcome(odd=1.65, prob=0.60, market="h2h", name="Arsenal", point=None, event_id="e1", ev=None):
    return ComparedOutcome(
        event_id=event_id, sport_key="soccer_epl", home_team="Arsenal", away_team="Chelsea",
        commence_time=NOW + timedelta(days=1), market=market, outcome_name=name, point=point,
        selection=name, betclic_odd=odd, pinnacle_odd=round(1 / prob * 1.03, 2), fair_prob=prob,
        ev=prob * odd - 1 if ev is None else ev, pinnacle_overround=1.03, betclic_overround=1.07,
        best_in_grid=True)


@pytest.mark.parametrize("odd, profile", [
    (1.39, None), (1.40, "SAFE"), (1.799, "SAFE"),
    (1.80, "SWEET_SPOT"), (2.349, "SWEET_SPOT"),
    (2.35, "AUDACIEUX"), (3.80, "AUDACIEUX"), (3.81, None),
])
def test_profile_odd_ranges(odd, profile):
    assert classify_profile(odd) == profile


class TestRejection:
    def test_ev_floor_inclusive(self):
        assert rules.MIN_EV == -0.08
        assert rejection_reason("SWEET_SPOT", outcome(2.0, 0.5, ev=-0.08), 0.9) is None
        assert rejection_reason("SWEET_SPOT", outcome(2.0, 0.5, ev=-0.081), 0.9) == REJECT_EV

    def test_standard_margin_needs_15_stats_points(self):
        """EV entre −8 % et −3.5 % : stats disponibles et ≥ 15/30 (convergence ≥ 0.50) obligatoires."""
        low = outcome(2.0, 0.47, ev=-0.06)
        assert rejection_reason("SWEET_SPOT", low, 0.50) is None
        assert rejection_reason("SWEET_SPOT", low, 0.49) == REJECT_STATS  # seuil Sweet Spot = 0.50
        assert rejection_reason("AUDACIEUX", replace(low, betclic_odd=3.0), 0.45) == REJECT_LOW_EV_STATS
        assert rejection_reason("AUDACIEUX", replace(low, betclic_odd=3.0), None) == REJECT_LOW_EV_STATS
        # À −3.5 % pile et au-dessus, pas d'exigence supplémentaire (stats absentes = 12/30 tolérées)
        assert rejection_reason("SWEET_SPOT", outcome(2.0, 0.5, ev=-0.035), None) is None

    def test_out_of_profiles(self):
        assert rejection_reason(None, outcome(5.0, 0.2), 0.9) == REJECT_ODD

    def test_safe_needs_56_percent(self):
        assert rejection_reason("SAFE", outcome(1.75, 0.559), 0.9) == REJECT_SAFE_PROB
        assert rejection_reason("SAFE", outcome(1.75, 0.56), 0.9) is None

    def test_safe_needs_stats(self):
        assert rejection_reason("SAFE", outcome(1.65, 0.60), None) == REJECT_SAFE_NO_STATS

    def test_sweet_and_audacious_accept_missing_stats(self):
        assert rejection_reason("SWEET_SPOT", outcome(2.0, 0.50), None) is None
        assert rejection_reason("AUDACIEUX", outcome(3.0, 0.33), None) is None

    @pytest.mark.parametrize("profile, threshold", list(rules.MIN_STATS_SCORE.items()))
    def test_stats_threshold(self, profile, threshold):
        odd = {"SAFE": 1.65, "SWEET_SPOT": 2.0, "AUDACIEUX": 3.0}[profile]
        o = outcome(odd, 0.62 if profile == "SAFE" else 0.33, ev=0.0)
        assert rejection_reason(profile, o, threshold) is None
        assert rejection_reason(profile, o, threshold - 0.01) == REJECT_STATS


class TestConvergence:
    def test_h2h_favours_stronger_team(self, strong_home, weak_away):
        assert team_rating(strong_home, True) > 0.8
        assert team_rating(weak_away, False) < 0.3
        home_pick = stats_convergence(outcome(name="Arsenal"), strong_home, weak_away)
        away_pick = stats_convergence(outcome(4.0, 0.2, name="Chelsea"), strong_home, weak_away)
        assert home_pick.score > 0.85
        assert away_pick.score < 0.15
        assert any("forme VVVVV" in f for f in home_pick.facts)

    def test_missing_stats_is_neutral(self, strong_home):
        conv = stats_convergence(outcome(), strong_home, None)
        assert conv.score is None
        assert "indisponibles" in conv.risks[0][1]

    def test_totals_over_high_scoring_teams(self, strong_home, weak_away):
        over = stats_convergence(outcome(2.05, 0.5, "totals", "Over", 2.5), strong_home, weak_away)
        under = stats_convergence(outcome(1.72, 0.5, "totals", "Under", 2.5), strong_home, weak_away)
        assert over.score > 0.6 and under.score < 0.4
        assert over.score + under.score == pytest.approx(1.0)
        assert "Total attendu" in over.facts[0]

    def test_spreads_uses_goal_difference(self, strong_home, weak_away):
        conv = stats_convergence(outcome(2.0, 0.5, "spreads", "Arsenal", -1.5), strong_home, weak_away)
        assert conv.score > 0.5

    def test_nba_back_to_back_and_injuries(self):
        lakers = make_team("Lakers", [(110, 100)] * 5, sport="basketball", size=15,
                           last_date=NOW + timedelta(hours=10),
                           injuries=["A (Out — Knee)", "B (Out — Hip)", "C (Day-To-Day)"])
        bulls = make_team("Bulls", [(100, 110)] * 5, sport="basketball", size=15, rank=14)
        o = replace(outcome(1.6, 0.6), home_team="Lakers", away_team="Bulls", outcome_name="Lakers")
        conv = stats_convergence(o, lakers, bulls)
        risks = [text for _, text in sorted(conv.risks, reverse=True)]
        assert risks[0].startswith("Back-to-back")
        assert any("3 joueurs incertains" in r for r in risks)


def test_analyze_fixture_event(soccer_event, now, strong_home, weak_away):
    stats = DetectionStats()
    opps = {}
    for o in compare_event(soccer_event, now=now, stats=stats):
        opp = analyze(o, "Football", "Premier League", 1000, strong_home, weak_away, stats)
        if opp:
            opps[opp.selection] = opp
    assert set(opps) == {"Arsenal", "Plus de 2.5"}
    assert stats.rejections == {REJECT_EV: 2, REJECT_ODD: 1}  # Nul et Under trop mal payés, Chelsea à 5.00
    assert stats.candidates == {"SAFE": 1, "SWEET_SPOT": 1}
    assert [(p, label.split(" · ")[1]) for _, p, label in sorted(stats.near_misses, reverse=True)] == [
        ("SAFE", "Moins de 2.5 @ 1.72"), ("AUDACIEUX", "Match nul @ 3.60")]  # EV −14 % puis −15.5 %

    arsenal = opps["Arsenal"]
    assert arsenal.profile == "SAFE"
    assert (arsenal.stake, arsenal.stake_pct) == (100.0, 0.10)  # 10 % de 1 000 €
    assert arsenal.score == round(arsenal.score_market + arsenal.score_price + arsenal.score_stats)
    assert 3 <= len(arsenal.arguments) <= 4
    assert "Pinnacle" in arsenal.arguments[0]
    assert arsenal.vigilance  # toujours un point de vigilance
    assert any("Marge bookmaker" in v for v in arsenal.vigilance)  # EV négative

    over = opps["Plus de 2.5"]
    assert over.profile == "SWEET_SPOT" and over.stake == 70.0  # 7 %
    assert "vraie value" in over.arguments[1]  # EV positive


def test_score_pillars():
    o = outcome(2.0, 0.48, ev=-0.015)  # SWEET_SPOT, EV à mi-chemin de −8 % et +5 %
    opp = analyze(o, "Football", "Premier League", 1000, None, None)
    assert opp.score_market == pytest.approx(35 * (0.48 - 0.40) / 0.16, abs=0.05)
    assert opp.score_price == pytest.approx(17.5, abs=0.05)
    assert opp.score_stats == pytest.approx(30 * rules.NEUTRAL_STATS_SCORE)
    assert opp.stats_convergence is None


def _opp(event_id, profile, score, odd):
    base = analyze(outcome(odd, 0.62 if profile == "SAFE" else 0.40, event_id=event_id, ev=0.0),
                   "Football", "Premier League", 1000,
                   *((make_team("Arsenal", [(2, 0)] * 5), make_team("Chelsea", [(0, 2)] * 5, rank=18))
                     if profile == "SAFE" else (None, None)))
    assert base.profile == profile
    return replace(base, score=score)


def test_select_top_diversifies_profiles_and_dedupes_matches():
    opps = [
        _opp("a", "SWEET_SPOT", 80, 2.0), _opp("a", "SAFE", 70, 1.6),
        _opp("b", "SWEET_SPOT", 78, 2.1), _opp("c", "SWEET_SPOT", 77, 2.2),
        _opp("d", "SWEET_SPOT", 76, 2.0), _opp("e", "SWEET_SPOT", 75, 2.0),
        _opp("f", "SAFE", 40, 1.5), _opp("g", "AUDACIEUX", 30, 3.0),
    ]
    picks = select_top(opps)
    assert len(picks) == rules.MAX_PICKS_PER_SCAN
    assert len({p.event_id for p in picks}) == len(picks)  # un seul pari par match
    assert {p.profile for p in picks} == set(rules.PROFILES)  # Safe et Audacieux repêchés
    assert [p.score for p in picks] == sorted((p.score for p in picks), reverse=True)
    # Match « a » : le Safe (stats très convergentes) l'emporte sur le Sweet Spot sans stats
    assert next(p for p in picks if p.event_id == "a").profile == "SAFE"


def _market_opp(event_id, market, score, conv):
    base = _opp(event_id, "SWEET_SPOT", score, 2.0)
    return replace(base, market=market, outcome_name=market, stats_convergence=conv)


def test_select_top_prefers_most_convergent_market_and_varies_markets():
    opps = [
        _market_opp("m1", "h2h", 70, 0.55), _market_opp("m1", "btts", 65, 0.80),   # BTTS plus convergent
        _market_opp("m2", "h2h", 69, 0.70), _market_opp("m2", "totals", 60, 0.60),
        _market_opp("m3", "h2h", 68, 0.70), _market_opp("m3", "dnb", 50, 0.65),
        _market_opp("m4", "h2h", 67, 0.90), _market_opp("m4", "double_chance", 55, 0.70),
    ]
    picks = {p.event_id: p.market for p in select_top(opps)}
    assert picks["m1"] == "btts"
    assert list(picks.values()).count("h2h") == rules.MAX_PICKS_PER_MARKET  # plafond de 2 par marché
    assert picks["m2"] == "h2h" and picks["m3"] == "h2h"  # matchs aux meilleurs scores
    assert picks["m4"] == "double_chance"  # h2h déjà pris deux fois → marché suivant du match


def test_select_top_fills_without_cap_when_only_one_market():
    opps = [_market_opp(f"t{i}", "h2h", 60 - i, 0.5) for i in range(4)]
    assert len(select_top(opps)) == 4


def test_select_top_with_few_candidates():
    assert select_top([]) == []
    single = [_opp("a", "AUDACIEUX", 50, 3.0)]
    assert select_top(single) == single
