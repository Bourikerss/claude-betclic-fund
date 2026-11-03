import pytest

from betclic_bot.devig import devig_multiplicative, devig_power, fair_probabilities, overround
from betclic_bot import rules
from betclic_bot.value import expected_value, profile_stake


class TestDevig:
    def test_multiplicative_normalises(self):
        probs = devig_multiplicative([1.95, 1.95])
        assert probs == pytest.approx([0.5, 0.5])

    def test_multiplicative_three_way(self):
        odds = [1.80, 3.90, 4.60]
        probs = devig_multiplicative(odds)
        assert sum(probs) == pytest.approx(1.0)
        assert probs[0] == pytest.approx((1 / 1.80) / overround(odds))

    def test_power_sums_to_one_and_favours_favourite(self):
        odds = [1.80, 3.90, 4.60]
        power, mult = devig_power(odds), devig_multiplicative(odds)
        assert sum(power) == pytest.approx(1.0)
        assert power[0] > mult[0]
        assert power[2] < mult[2]

    def test_invalid_inputs(self):
        with pytest.raises(ValueError):
            devig_multiplicative([1.9])
        with pytest.raises(ValueError):
            devig_multiplicative([1.0, 2.0])
        with pytest.raises(ValueError):
            fair_probabilities([2.0, 2.0], method="shin")


class TestValue:
    def test_expected_value(self):
        assert expected_value(0.5, 2.10) == pytest.approx(0.05)

    @pytest.mark.parametrize("profile, pct, at10, at20", [
        ("SAFE", 0.10, 1.00, 2.00),
        ("SWEET_SPOT", 0.07, 0.70, 1.40),
        ("AUDACIEUX", 0.05, 0.50, 1.00),
        ("COMBINE", 0.05, 0.50, 1.00),
    ])
    def test_stake_is_proportional_to_balance(self, profile, pct, at10, at20):
        """Demande du 03/11/2026 : si la bankroll passe de 10 à 20 €, les mises doublent."""
        assert profile_stake(profile, 10.0) == (at10, pct, at10)
        assert profile_stake(profile, 20.0)[0] == at20

    def test_stake_floor_050(self):
        assert profile_stake("AUDACIEUX", 6.0) == (0.50, 0.05, 0.30)
        assert profile_stake("SAFE", 4.0)[0] == 0.50
        assert profile_stake("SAFE", 200.0)[0] == 20.0  # aucun plafond
