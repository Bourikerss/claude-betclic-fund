import json
from datetime import timedelta

import pytest

from betclic_bot.ledger import LOST, VOID, WON, Ledger

from conftest import NOW


def _bet(bid, odd=2.0, kind="SIMPLE"):
    return {"id": bid, "kind": kind, "label": f"Pari {bid}", "odd": odd, "legs": [], "profile": "SAFE"}


def test_new_ledger_starts_at_10(tmp_path):
    led = Ledger(tmp_path / "ledger.json", 10.0, NOW)
    assert led.balance == 10.0
    assert led.operations[0]["type"] == "DEPOT"
    m = led.metrics()
    assert (m.equity, m.profit, m.roi, m.winrate, m.max_drawdown) == (10.0, 0.0, 0.0, None, 0.0)


def test_operations_track_balance_like_a_bank_account(tmp_path):
    led = Ledger(tmp_path / "ledger.json", 10.0, NOW)
    led.place(_bet("a", 2.0), 1.0, NOW)
    led.place(_bet("b", 1.5), 0.7, NOW)
    assert led.balance == 8.3
    assert [o["amount"] for o in led.operations] == [10.0, -1.0, -0.7]
    led.settle("a", WON, NOW + timedelta(hours=3), "2-0")
    led.settle("b", LOST, NOW + timedelta(hours=4), "0-1")
    assert led.balance == 10.3  # 8.3 + gain de 2.00
    assert [o["type"] for o in led.operations] == ["DEPOT", "MISE", "MISE", "GAIN", "PERTE"]
    assert [o["balance"] for o in led.operations][-2:] == [10.3, 10.3]
    m = led.metrics()
    assert m.profit == pytest.approx(0.3) and m.equity == 10.3
    assert m.roi == pytest.approx(0.03)
    assert m.yield_ == pytest.approx(0.3 / 1.7)
    assert m.winrate == 0.5
    assert m.max_drawdown == pytest.approx(0.7)  # 11.00 → 10.30


def test_void_refunds_stake(tmp_path):
    led = Ledger(tmp_path / "ledger.json", 10.0, NOW)
    led.place(_bet("a"), 1.0, NOW)
    led.settle("a", VOID, NOW, "1-1")
    assert led.balance == 10.0 and led.bets["a"]["profit"] == 0.0
    assert led.metrics().staked_settled == 0.0


def test_persistence_and_guards(tmp_path):
    path = tmp_path / "ledger.json"
    led = Ledger(path, 10.0, NOW)
    led.place(_bet("a"), 1.0, NOW)
    led.save()
    again = Ledger(path)
    assert again.balance == 9.0 and again.has_bet("a")
    assert json.loads(path.read_text())["initial"] == 10.0
    with pytest.raises(ValueError):
        again.place(_bet("a"), 1.0, NOW)       # déjà engagé
    with pytest.raises(ValueError):
        again.place(_bet("b"), 50.0, NOW)      # au-delà du solde


def test_daily_budget_is_35_percent_of_start_of_day(tmp_path):
    led = Ledger(tmp_path / "ledger.json", 10.0, NOW)
    assert led.daily_budget(NOW) == 3.5
    led.place(_bet("a"), 1.0, NOW)
    assert led.daily_budget(NOW) == 2.5          # 35 % de 10 € moins 1 € déjà misé
    assert led.daily_budget(NOW + timedelta(days=1)) == pytest.approx(0.35 * 9.0)  # nouveau jour
