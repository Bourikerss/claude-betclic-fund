import json
import time

import pytest
import requests

from betclic_bot.stats_client import StatsClient, best_match, name_similarity, normalize_team


@pytest.mark.parametrize("odds_api, espn", [
    ("Brighton and Hove Albion", "Brighton & Hove Albion"),
    ("Paris Saint Germain", "Paris Saint-Germain"),
    ("Inter Milan", "Internazionale"),
    ("Athletic Bilbao", "Athletic Club"),
    ("Rennes", "Stade Rennais"),
    ("Lyon", "Olympique Lyonnais"),
    ("Borussia Monchengladbach", "Borussia Mönchengladbach"),
    ("1. FC Köln", "FC Cologne"),
    ("FSV Mainz 05", "Mainz"),
    ("Los Angeles Clippers", "LA Clippers"),
    ("Sporting Lisbon", "Sporting CP"),
    ("Feyenoord", "Feyenoord Rotterdam"),
    ("Olympiakos Piraeus", "Olympiacos"),
    ("Salzburg", "RB Salzburg"),
    ("PFC Levski Sofia", "Levski Sofia"),
    ("Omonoia FC", "Omonia Nicosia"),
    ("LASK", "LASK Linz"),
    ("Slavia Praha", "Slavia Prague"),
    ("Ferencváros TC", "Ferencvaros"),
])
def test_fuzzy_matching_known_names(odds_api, espn):
    candidates = [espn, "Manchester United", "AC Milan", "Paris FC", "Real Sociedad", "Los Angeles Lakers"]
    assert best_match(odds_api, candidates) == espn


@pytest.mark.parametrize("a, b", [
    ("Manchester City", "Manchester United"),
    ("Inter Milan", "AC Milan"),
    ("Paris FC", "Paris Saint-Germain"),
    ("Real Madrid", "Real Sociedad"),
])
def test_fuzzy_matching_never_confuses_rivals(a, b):
    assert name_similarity(a, b) < 0.75


def test_unknown_team_returns_none():
    assert best_match("Wolverhampton Wanderers", ["Arsenal", "Chelsea"]) is None


def test_normalize_team():
    assert normalize_team("AFC Bournemouth") == "bournemouth"
    assert normalize_team("Atlético Madrid") == "atletico madrid"


# --- client HTTP simulé -------------------------------------------------------------
STANDINGS = {"children": [{"standings": {"entries": [
    {"team": {"id": "359", "displayName": "Arsenal"}, "stats": [
        {"name": "rank", "value": 1}, {"name": "wins", "value": 8}, {"name": "ties", "value": 0},
        {"name": "losses", "value": 1}, {"name": "pointsFor", "value": 14}, {"name": "pointsAgainst", "value": 5}]},
    {"team": {"id": "363", "displayName": "Chelsea"}, "stats": [
        {"name": "rank", "value": 9}, {"name": "wins", "value": 4}, {"name": "ties", "value": 2},
        {"name": "losses", "value": 3}, {"name": "pointsFor", "value": 12}, {"name": "pointsAgainst", "value": 11}]},
]}}]}


def _game(event_id, date, home_id, away_id, hs, as_, completed=True):
    return {"id": event_id, "date": date, "competitions": [{
        "status": {"type": {"completed": completed}},
        "competitors": [
            {"homeAway": "home", "team": {"id": home_id, "displayName": "Arsenal" if home_id == "359" else "Adv"},
             "score": {"value": hs}},
            {"homeAway": "away", "team": {"id": away_id, "displayName": "Arsenal" if away_id == "359" else "Adv"},
             "score": {"value": as_}},
        ]}]}


SCHEDULE = {"events": [
    _game("1", "2026-08-21T19:00Z", "359", "1", 3, 0),
    _game("2", "2026-11-01T16:30Z", "2", "359", 0, 1),
    _game("3", "2026-10-24T14:00Z", "359", "3", 2, 2),
    _game("9", "2026-12-24T14:00Z", "359", "4", None, None, completed=False),
]}


class Resp:
    def __init__(self, data, status=200):
        self._data, self.status_code = data, status

    def json(self):
        return self._data


class FakeSession:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def get(self, url, timeout):
        self.calls.append(url)
        if self.fail:
            raise requests.ConnectionError("hors ligne")
        if url.endswith("/standings"):
            return Resp(STANDINGS if "eng.1" in url else {"children": []})
        if "/teams/359/schedule" in url and "eng.1" in url:
            return Resp(SCHEDULE)
        return Resp({"events": []})


def test_team_stats_from_espn(tmp_path):
    session = FakeSession()
    stats = StatsClient(tmp_path, session=session).team_stats("soccer_epl", "Arsenal FC")
    assert stats.name == "Arsenal" and stats.rank == 1 and stats.table_size == 2
    assert (stats.wins, stats.draws, stats.losses) == (8, 0, 1)
    assert [g.result for g in stats.games] == ["V", "N", "V"]  # du plus récent au plus ancien, match à venir exclu
    assert stats.form == "VNV"
    assert stats.venue_record(True) == (1, 1, 0)
    assert stats.venue_record(False) == (1, 0, 0)
    assert stats.avg_scored == pytest.approx(2.0)  # 3 matchs : moyenne calculée sur les résultats


def test_cache_avoids_second_call_and_expires(tmp_path):
    session = FakeSession()
    StatsClient(tmp_path, session=session).team_stats("soccer_epl", "Arsenal")
    first = len(session.calls)
    StatsClient(tmp_path, session=session).team_stats("soccer_epl", "Arsenal")  # nouveau process, cache disque
    assert len(session.calls) == first

    for path in tmp_path.glob("*.json"):
        data = json.loads(path.read_text())
        data["fetched"] = time.time() - 25 * 3600
        path.write_text(json.dumps(data))
    StatsClient(tmp_path, session=session).team_stats("soccer_epl", "Arsenal")
    assert len(session.calls) == 2 * first


def test_network_failure_uses_stale_cache_then_none(tmp_path):
    StatsClient(tmp_path, session=FakeSession()).team_stats("soccer_epl", "Arsenal")
    for path in tmp_path.glob("*.json"):
        data = json.loads(path.read_text())
        data["fetched"] = 0
        path.write_text(json.dumps(data))
    stale = StatsClient(tmp_path, session=FakeSession(fail=True)).team_stats("soccer_epl", "Arsenal")
    assert stale is not None and stale.rank == 1
    assert StatsClient(tmp_path / "vide", session=FakeSession(fail=True)).team_stats("soccer_epl", "Arsenal") is None


def test_unsupported_sport(tmp_path):
    client = StatsClient(tmp_path, session=FakeSession())
    assert not client.supports("tennis_atp_paris_masters")
    assert client.match_stats("tennis_atp_paris_masters", "A", "B") == (None, None)


def test_european_match_uses_domestic_league(tmp_path):
    """Ligue des Champions : classement et bilan du championnat national, pondérés par sa force."""
    ucl = {"children": [{"standings": {"entries": [
        {"team": {"id": "359", "displayName": "Arsenal"}, "stats": [
            {"name": "rank", "value": 20}, {"name": "wins", "value": 1}, {"name": "ties", "value": 0},
            {"name": "losses", "value": 2}, {"name": "pointsFor", "value": 3}, {"name": "pointsAgainst", "value": 5}]},
    ] + [{"team": {"id": str(i), "displayName": f"Club {i}"}, "stats": []} for i in range(35)]}}]}

    class Session(FakeSession):
        def get(self, url, timeout):
            self.calls.append(url)
            if url.endswith("uefa.champions/standings"):
                return Resp(ucl)
            return super().get(url, timeout)

    stats = StatsClient(tmp_path, session=Session()).team_stats("soccer_uefa_champs_league", "Arsenal")
    assert (stats.rank, stats.table_size, stats.competition_name) == (1, 2, "Premier League")
    assert (stats.wins, stats.losses) == (8, 1)
    assert (stats.european_rank, stats.european_size) == (20, 36)
    assert stats.league_strength == 1.0
