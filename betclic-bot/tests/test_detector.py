import copy

import pytest

from betclic_bot.detector import DetectionStats, compare_event, group_outcomes, selection_label
from betclic_bot.devig import devig_multiplicative


def _by_selection(event, now, **kw):
    return {o.selection: o for o in compare_event(event, now=now, **kw)}


def test_compares_every_betclic_outcome(soccer_event, now):
    outcomes = _by_selection(soccer_event, now)
    assert set(outcomes) == {"Arsenal", "Chelsea", "Match nul", "Plus de 2.5", "Moins de 2.5"}

    arsenal = outcomes["Arsenal"]
    p_home = devig_multiplicative([1.62, 5.60, 4.10])[0]
    assert arsenal.fair_prob == pytest.approx(p_home)
    assert arsenal.ev == pytest.approx(p_home * 1.65 - 1)
    assert arsenal.betclic_overround == pytest.approx(1 / 1.65 + 1 / 5.00 + 1 / 3.60)
    assert arsenal.best_in_grid  # issue la mieux payée du 1N2 Betclic

    over = outcomes["Plus de 2.5"]
    assert over.fair_prob == pytest.approx(0.5)
    assert over.ev == pytest.approx(0.025)
    assert over.point == 2.5
    assert over.best_in_grid and not outcomes["Moins de 2.5"].best_in_grid


def test_started_match_ignored(soccer_event, now):
    soccer_event["commence_time"] = "2026-11-02T11:00:00Z"
    assert compare_event(soccer_event, now=now) == []


def test_missing_bookmaker(soccer_event, now):
    soccer_event["bookmakers"] = soccer_event["bookmakers"][1:]
    stats = DetectionStats()
    assert compare_event(soccer_event, now=now, stats=stats) == []
    assert stats.skipped == {"match sans Pinnacle": 1}


def test_two_way_vs_three_way_h2h_is_skipped(soccer_event, now):
    """Pinnacle sans « Draw » → probabilités 2 voies non comparables au 1N2 Betclic."""
    pin = soccer_event["bookmakers"][0]["markets"][0]
    pin["outcomes"] = [o for o in pin["outcomes"] if o["name"] != "Draw"]
    stats = DetectionStats()
    assert {o.market for o in compare_event(soccer_event, now=now, stats=stats)} == {"totals"}
    assert stats.skipped["h2h : 1N2 d'un côté, 2 issues de l'autre"] == 1


def test_spreads_matched_on_same_line(soccer_event, now):
    event = copy.deepcopy(soccer_event)
    event["bookmakers"][1]["markets"][2]["outcomes"] = [{"name": "Arsenal", "price": 2.05, "point": -0.5},
                                                        {"name": "Chelsea", "price": 1.70, "point": 0.5}]
    outcomes = _by_selection(event, now)
    expected_p = devig_multiplicative([1.90, 2.00])[0]
    assert outcomes["Arsenal -0.5"].fair_prob == pytest.approx(expected_p)


def test_aberrant_margin_skipped(soccer_event, now):
    for o in soccer_event["bookmakers"][0]["markets"][1]["outcomes"]:
        o["price"] = 1.60  # marge 25 %
    assert {o.market for o in compare_event(soccer_event, now=now)} == {"h2h"}


def test_detection_stats(soccer_event, now):
    stats = DetectionStats()
    compare_event(soccer_event, now=now, stats=stats)
    assert (stats.events, stats.events_with_both) == (1, 1)
    assert stats.compared == {"h2h": 1, "totals": 1}
    assert stats.skipped == {"spreads : ligne Betclic absente chez Pinnacle": 1}


def test_group_outcomes_spreads_home_perspective():
    groups = group_outcomes("spreads", [{"name": "A", "price": 1.9, "point": -1.5},
                                        {"name": "B", "price": 1.9, "point": 1.5}], home="A")
    assert list(groups) == [-1.5]
    assert set(groups[-1.5]) == {"A", "B"}


def test_selection_labels():
    assert selection_label("h2h", "Draw", None) == "Match nul"
    assert selection_label("totals", "Under", 215.5) == "Moins de 215.5"
    assert selection_label("spreads", "Lakers", 4.5) == "Lakers +4.5"
