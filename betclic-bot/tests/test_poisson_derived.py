import pytest

from betclic_bot import rules
from betclic_bot.derived import derive_outcomes, prior_total
from betclic_bot.detector import compare_event
from betclic_bot.devig import devig_multiplicative
from betclic_bot.poisson import ScoreModel, fit


class TestPoisson:
    def test_probabilities_sum_to_one(self):
        m = ScoreModel(1.6, 1.1)
        assert sum(m.h2h()) == pytest.approx(1.0, abs=1e-9)
        assert m.over(2.5) + m._sum(lambda i, j: i + j <= 2) == pytest.approx(1.0)

    def test_known_values(self):
        m = ScoreModel(1.0, 1.0)
        assert m.team_over(True, 0.5) == pytest.approx(1 - 2.718281828 ** -1, abs=1e-6)
        assert m.btts() == pytest.approx((1 - 2.718281828 ** -1) ** 2, abs=1e-6)

    def test_fit_reproduces_pinnacle(self):
        target, over = (0.50, 0.26, 0.24), (2.5, 0.55)
        m = fit(target, over=over)
        p1, px, p2 = m.h2h()
        assert p1 == pytest.approx(0.50, abs=0.02) and p2 == pytest.approx(0.24, abs=0.02)
        assert m.over(2.5) == pytest.approx(0.55, abs=0.02)
        assert m.lambda_home > m.lambda_away

    def test_prior_total_drives_goal_level_without_totals(self):
        low, high = fit((0.45, 0.28, 0.27), prior_total=2.0), fit((0.45, 0.28, 0.27), prior_total=3.4)
        assert high.over(2.5) > low.over(2.5)


def test_derived_markets(soccer_event, now, strong_home, weak_away):
    h2h = compare_event(soccer_event, now=now)
    derived = derive_outcomes(soccer_event, h2h, strong_home, weak_away)
    by = {(o.market, o.outcome_name, o.point): o for o in derived}
    p1, p2, px = devig_multiplicative([1.62, 5.60, 4.10])

    assert by[("double_chance", "1X", None)].fair_prob == pytest.approx(p1 + px)
    assert by[("dnb", "Arsenal", None)].fair_prob == pytest.approx(p1 / (p1 + p2))
    yes, no = by[("btts", "Yes", None)], by[("btts", "No", None)]
    assert yes.fair_prob + no.fair_prob == pytest.approx(1.0)
    # Ligne 2.5 cotée par Pinnacle : sa probabilité prime sur le modèle
    assert by[("totals", "Over", 2.5)].fair_prob == pytest.approx(0.5)
    assert by[("totals", "Over", 1.5)].fair_prob > by[("totals", "Over", 3.5)].fair_prob
    assert by[("spreads", "Arsenal", -1.5)].fair_prob + by[("spreads", "Chelsea", 1.5)].fair_prob == pytest.approx(1)
    assert ("team_totals", "Arsenal Over", 1.5) in by

    o = by[("double_chance", "1X", None)]
    margin = h2h[0].betclic_overround
    assert o.estimated and o.betclic_odd == pytest.approx(1 / o.fair_prob / margin)
    # EV estimée = 1 / marge 1N2 Betclic − 1, sans effet d'arrondi
    assert o.ev == pytest.approx(1 / margin - 1)
    assert all(d.ev == pytest.approx(1 / margin - 1) for d in derived)
    assert o.min_odd == pytest.approx(1 / o.fair_prob * (1 + rules.MIN_EV), abs=0.011)
    assert o.selection == "Arsenal ou nul"


def test_derived_requires_full_1x2(soccer_event, now):
    h2h = [o for o in compare_event(soccer_event, now=now) if o.outcome_name != "Draw"]
    assert derive_outcomes(soccer_event, h2h, None, None) == []


def test_prior_total(strong_home, weak_away):
    # (attaque Arsenal + défense Chelsea)/2 + (attaque Chelsea + défense Arsenal)/2
    expected = (16 / 6 + 11 / 6) / 2 + (5 / 6 + 3 / 6) / 2
    assert prior_total(strong_home, weak_away) == pytest.approx(expected)
    assert prior_total(None, weak_away) is None
