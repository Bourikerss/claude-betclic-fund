from datetime import timedelta

import pytest

from betclic_bot.auto_settle import AutoSettler, combine, evaluate_leg
from betclic_bot.ledger import LOST, PENDING, VOID, WON, Ledger, iso

from conftest import NOW


@pytest.mark.parametrize("market, outcome, point, score, expected", [
    ("h2h", "Porto", None, (2, 1), WON), ("h2h", "Draw", None, (1, 1), WON), ("h2h", "Napoli", None, (2, 1), LOST),
    ("double_chance", "1X", None, (1, 1), WON), ("double_chance", "X2", None, (2, 0), LOST),
    ("dnb", "Porto", None, (0, 0), VOID), ("dnb", "Napoli", None, (0, 1), WON),
    ("btts", "Yes", None, (1, 1), WON), ("btts", "No", None, (2, 1), LOST),
    ("totals", "Over", 2.5, (2, 1), WON), ("totals", "Under", 2.5, (2, 1), LOST), ("totals", "Over", 2.0, (1, 1), VOID),
    ("team_totals", "Porto Over", 1.5, (2, 0), WON), ("team_totals", "Napoli Under", 0.5, (3, 1), LOST),
    ("spreads", "Porto", -1.5, (3, 1), WON), ("spreads", "Napoli", 1.5, (3, 1), LOST), ("spreads", "Napoli", 1.5, (2, 1), WON),
])
def test_evaluate_leg(market, outcome, point, score, expected):
    assert evaluate_leg(market, outcome, point, "Porto", "Napoli", *score) == expected


def test_combine_statuses():
    assert combine([WON, WON]) == WON
    assert combine([WON, LOST, PENDING]) == LOST
    assert combine([WON, PENDING]) == PENDING
    assert combine([WON, VOID]) == WON
    assert combine([VOID, VOID]) == VOID


class FakeStats:
    def __init__(self, events):
        self.events, self.urls = events, []

    def get_json(self, url, max_age=None):
        self.urls.append((url, max_age))
        return {"events": self.events if "20261104" in url else []}


def _espn(home, away, hs, as_, status="STATUS_FULL_TIME"):
    return {"competitions": [{"status": {"type": {"name": status}}, "competitors": [
        {"homeAway": "home", "team": {"displayName": home}, "score": str(hs)},
        {"homeAway": "away", "team": {"displayName": away}, "score": str(as_)}]}]}


def _leg(home, away, market, outcome, odd, point=None):
    return {"event_id": f"{home}-{away}", "sport_key": "soccer_uefa_champs_league", "home": home, "away": away,
            "kickoff": "2026-11-04T20:00:00Z", "market": market, "outcome_name": outcome, "point": point,
            "odd": odd, "status": PENDING, "final_score": None}


def test_settler_settles_singles_and_combo(tmp_path):
    led = Ledger(tmp_path / "l.json", 10.0, NOW)
    led.place({"id": "s1", "kind": "SIMPLE", "label": "Porto", "odd": 1.85,
               "legs": [_leg("Porto", "Napoli", "h2h", "Porto", 1.85)]}, 1.0, NOW)
    led.place({"id": "c1", "kind": "COMBINE", "label": "Combiné", "odd": 2.04,
               "legs": [_leg("PSV Eindhoven", "Club Brugge", "btts", "Yes", 1.40),
                        _leg("Porto", "Napoli", "totals", "Over", 1.46, 1.5)]}, 0.5, NOW)
    stats = FakeStats([_espn("FC Porto", "Napoli", 2, 1), _espn("PSV Eindhoven", "Club Brugge", 1, 1)])
    report = AutoSettler(stats).run(led, NOW + timedelta(days=2, hours=12))
    assert {b["id"]: b["status"] for b in report.settled} == {"s1": WON, "c1": WON}
    assert led.bets["s1"]["final_score"] == "2-1"
    assert led.bets["c1"]["payout"] == round(0.5 * 1.40 * 1.46, 2)
    assert led.balance == round(10 - 1 - 0.5 + 1.85 + 0.5 * 1.40 * 1.46, 2)
    assert all(age == 3600 for _, age in stats.urls)  # scores frais, pas le cache 24 h


def test_settler_waits_for_kickoff_and_handles_postponed(tmp_path):
    led = Ledger(tmp_path / "l.json", 10.0, NOW)
    led.place({"id": "s1", "kind": "SIMPLE", "label": "Porto", "odd": 1.85,
               "legs": [_leg("Porto", "Napoli", "h2h", "Porto", 1.85)]}, 1.0, NOW)
    settler = AutoSettler(FakeStats([_espn("Porto", "Napoli", 0, 0, "STATUS_POSTPONED")]))
    early = settler.run(led, NOW + timedelta(days=1))
    assert early.settled == [] and early.still_open == 1  # match pas encore joué
    late = settler.run(led, NOW + timedelta(days=3))
    assert late.settled[0]["status"] == VOID and led.balance == 10.0


def test_unknown_match_voided_after_3_days(tmp_path):
    led = Ledger(tmp_path / "l.json", 10.0, NOW)
    led.place({"id": "s1", "kind": "SIMPLE", "label": "X", "odd": 2.0,
               "legs": [_leg("Inconnu FC", "Autre FC", "h2h", "Inconnu FC", 2.0)]}, 1.0, NOW)
    settler = AutoSettler(FakeStats([]))
    assert settler.run(led, NOW + timedelta(days=3)).settled == []
    assert settler.run(led, NOW + timedelta(days=6)).settled[0]["final_score"] == "match introuvable"
