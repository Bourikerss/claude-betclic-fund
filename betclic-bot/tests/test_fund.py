from dataclasses import replace
from datetime import timedelta

import pytest

from betclic_bot import rules
from betclic_bot.analyzer import analyze
from betclic_bot.combo import Combo, ComboLeg, best_combo, is_leg_candidate
from betclic_bot.detector import compare_event
from betclic_bot.fund import commit_plan, plan_day
from betclic_bot.ledger import Ledger
from betclic_bot.obsidian import ObsidianVault, split_frontmatter

from conftest import NOW, make_team
from test_analyzer import outcome


def _opp(event_id, profile, score, odd, prob):
    home, away = make_team("Arsenal", [(2, 0)] * 5), make_team("Chelsea", [(0, 2)] * 5, rank=18)
    o = analyze(outcome(odd, prob, event_id=event_id, ev=-0.02), "Football", "Premier League", 10.0, home, away)
    assert o is not None and o.profile == profile, (o and o.profile)
    return replace(o, score=score)


def _leg(event_id, odd, prob=0.70, conv=0.8):
    return ComboLeg(outcome(odd, prob, event_id=event_id, ev=-0.03), conv, f"stat {event_id}", "Football", "EPL")


@pytest.fixture
def ledger(tmp_path):
    return Ledger(tmp_path / "ledger.json", 10.0, NOW)


def test_plan_day_stakes_are_proportional_and_capped(ledger):
    cands = [_opp("a", "SAFE", 80, 1.6, 0.66), _opp("b", "SWEET_SPOT", 70, 2.0, 0.52),
             _opp("c", "SWEET_SPOT", 60, 2.1, 0.50), _opp("d", "AUDACIEUX", 50, 3.0, 0.36),
             _opp("e", "SWEET_SPOT", 40, 2.2, 0.47)]
    plan = plan_day(cands, [], ledger, NOW)
    stakes = {p.record["legs"][0]["event_id"]: p.record["stake"] for p in plan.singles}
    assert len(plan.singles) <= rules.MAX_PICKS_PER_SCAN
    assert stakes["a"] == 1.00 and stakes["b"] == 0.70  # Safe 10 %, Sweet Spot 7 % de 10 €
    assert plan.total_staked <= 0.35 * 10 + 1e-9        # plafond journalier
    assert all(s >= 0.50 for s in stakes.values())


def test_plan_doubles_with_bankroll(tmp_path):
    rich = Ledger(tmp_path / "rich.json", 20.0, NOW)
    plan = plan_day([_opp("a", "SAFE", 80, 1.6, 0.66)], [], rich, NOW)
    assert plan.singles[0].record["stake"] == 2.00


def test_plan_skips_events_already_open(ledger):
    first = plan_day([_opp("a", "SAFE", 80, 1.6, 0.66)], [], ledger, NOW)
    for p in first.positions:
        rec = dict(p.record); stake = rec.pop("stake"); ledger.place(rec, stake, NOW)
    again = plan_day([_opp("a", "SAFE", 80, 1.6, 0.66)], [], ledger, NOW + timedelta(hours=1))
    assert again.singles == []


def test_combo_of_the_day(ledger):
    legs = [_leg("x", 1.40), _leg("y", 1.46), _leg("z", 1.30, conv=0.65), _leg("a", 1.35)]
    plan = plan_day([_opp("a", "SAFE", 80, 1.6, 0.66)], legs, ledger, NOW)
    combo = plan.combo.record
    assert combo["kind"] == "COMBINE" and combo["profile"] == "COMBINE"
    assert rules.COMBO_MIN_ODD <= combo["odd"] <= rules.COMBO_MAX_ODD
    assert "a" not in {l["event_id"] for l in combo["legs"]}  # pas sur un match déjà joué en simple
    assert len({l["event_id"] for l in combo["legs"]}) == len(combo["legs"])
    assert combo["stake"] == 0.50  # 5 % de 10 €


def test_best_combo_respects_odds_window():
    assert best_combo([_leg("x", 1.20), _leg("y", 1.20)]) is None  # 1.44 < 1.70
    combo = best_combo([_leg("x", 1.40), _leg("y", 1.46), _leg("z", 1.70)])
    assert isinstance(combo, Combo) and 1.70 <= combo.odd <= 2.40
    assert combo.ev == pytest.approx(combo.fair_prob * combo.odd - 1)


def test_leg_candidate_rules():
    good = outcome(1.40, 0.70, ev=-0.02)
    assert is_leg_candidate(good, 0.7)
    assert not is_leg_candidate(good, None)                      # stats obligatoires
    assert not is_leg_candidate(good, 0.5)                       # convergence trop faible
    assert not is_leg_candidate(outcome(1.40, 0.55, ev=-0.02), 0.9)  # pas assez solide
    assert not is_leg_candidate(outcome(1.10, 0.90, ev=-0.01), 0.9)  # cote trop basse


def test_fun_bet_when_no_combo(ledger):
    plan = plan_day([_opp("a", "SAFE", 80, 1.6, 0.66), _opp("d", "AUDACIEUX", 50, 3.0, 0.36),
                     _opp("e", "AUDACIEUX", 45, 3.2, 0.33)], [], ledger, NOW)
    assert plan.combo is None or plan.combo.record["kind"] == "FUN"


def test_commit_plan_writes_ledger_and_notes(tmp_path, ledger, soccer_event, strong_home, weak_away):
    vault = ObsidianVault(tmp_path)
    opp = next(analyze(o, "Football", "Premier League", 10.0, strong_home, weak_away)
               for o in compare_event(soccer_event, now=NOW) if o.selection == "Arsenal")
    plan = plan_day([opp], [_leg("x", 1.40), _leg("y", 1.46)], ledger, NOW)
    commit_plan(plan, ledger, vault, NOW)
    assert ledger.balance == round(10 - plan.total_staked, 2)
    notes = sorted(p.name for p in (tmp_path / "02 - Paris Détectés").glob("*.md"))
    assert any("Combiné du jour" in n for n in notes) and any("Arsenal" in n for n in notes)
    meta, _ = split_frontmatter((tmp_path / "02 - Paris Détectés" / next(n for n in notes if "Combiné" in n)).read_text())
    assert meta["profil"] == "COMBINE" and meta["statut"] == "EN_ATTENTE"
    assert Ledger(tmp_path / "ledger.json").balance == ledger.balance  # sauvegardé


def test_combo_takes_priority_over_weakest_single(ledger):
    """03/11/2026 : 4 simples (3,20 €) laissaient 0,30 € → pas de combiné. Le plus faible simple cède sa place."""
    cands = [_opp("a", "SAFE", 80, 1.6, 0.66), _opp("b", "SAFE", 70, 1.55, 0.67),
             _opp("c", "SWEET_SPOT", 60, 2.0, 0.52), _opp("d", "AUDACIEUX", 50, 3.0, 0.36)]
    legs = [_leg("x", 1.40), _leg("y", 1.46)]
    plan = plan_day(cands, legs, ledger, NOW)
    assert plan.combo is not None and plan.combo.record["kind"] == "COMBINE"
    assert len(plan.singles) == 3
    assert "d" not in {p.record["legs"][0]["event_id"] for p in plan.singles}  # plus faible score retiré
    assert plan.total_staked <= 3.5 + 1e-9
    assert any("remplacé par le Combiné" in s for s in plan.skipped)


def test_combo_never_drops_below_two_singles(tmp_path):
    poor = Ledger(tmp_path / "poor.json", 4.0, NOW)  # plafond 1,40 € : deux simples à 0,50 € + combiné à 0,50 € = 1,50 €
    cands = [_opp("a", "SAFE", 80, 1.6, 0.66), _opp("b", "SAFE", 70, 1.55, 0.67)]
    plan = plan_day(cands, [_leg("x", 1.40), _leg("y", 1.46)], poor, NOW)
    assert len(plan.singles) == 2 and plan.combo is None
