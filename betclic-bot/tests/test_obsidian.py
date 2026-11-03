from dataclasses import replace
from datetime import timedelta

import pytest

from betclic_bot.analyzer import analyze
from betclic_bot.detector import compare_event
from betclic_bot.obsidian import ObsidianVault, split_frontmatter

REQUIRED_KEYS = ["sport", "ligue", "match", "date", "marche", "selection", "profil", "score_confiance",
                 "cote_betclic", "fair_odd_pinnacle", "probabilite_reelle", "ev_percent", "mise_recommandee",
                 "statut", "profit"]


@pytest.fixture
def bet(soccer_event, now, strong_home, weak_away):
    outcome = next(o for o in compare_event(soccer_event, now=now) if o.selection == "Arsenal")
    return analyze(outcome, "Football", "Premier League", 1000, strong_home, weak_away)


@pytest.fixture
def vault(tmp_path):
    return ObsidianVault(tmp_path)


def _read(path):
    return split_frontmatter(path.read_text(encoding="utf-8"))


def test_create_note_with_full_frontmatter(vault, bet, now):
    res = vault.upsert_bet(bet, 1000, now)
    assert res.created
    meta, body = _read(res.path)
    assert list(meta)[:len(REQUIRED_KEYS)] == REQUIRED_KEYS
    assert meta["statut"] == "EN_ATTENTE"
    assert meta["profit"] == 0
    assert meta["date"] == "2026-11-03T21:00"  # heure de Paris
    assert meta["cote_betclic"] == 1.65
    assert meta["profil"] == "SAFE"
    assert meta["score_confiance"] == bet.score
    assert meta["mise_recommandee"] == 100.0  # 10 % de 1 000 €
    assert (meta["mise_percent"], meta["mise_theorique"]) == (10.0, 100.0)
    assert "profil/safe" in meta["tags"]
    assert "[[Football]]" in body and "[[Premier League]]" in body
    for section in ("## 📊 Contexte sportif", "## 🧠 Argumentaire du pronostic", "## ⚠️ Point de vigilance",
                    "## 💰 Gestion de mise"):
        assert section in body
    assert "| Classement | 1/20 · Premier League | 15/20 · Premier League |" in body
    assert "Phase de ligue UEFA" not in body
    assert "`VVVVV`" in body  # forme d'Arsenal
    assert body.count("\n- ", body.index("## 🧠"), body.index("## ⚠️")) in (3, 4)
    assert res.path.name == "2026-11-03 - Arsenal vs Chelsea - Arsenal (Vainqueur).md"
    assert (vault.root / "04 - Sports & Ligues" / "Football.md").exists()
    assert (vault.root / "04 - Sports & Ligues" / "Premier League.md").exists()


def test_update_keeps_detection_values(vault, bet, now):
    vault.upsert_bet(bet, 1000, now)
    later = now + timedelta(hours=3)
    res = ObsidianVault(vault.root).upsert_bet(replace(bet, betclic_odd=2.0, ev=0.08), 1000, later)
    assert not res.created and res.updated
    meta, body = _read(res.path)
    assert meta["cote_betclic"] == 1.65
    assert meta["cote_betclic_actuelle"] == 2.0
    assert meta["ev_actuel_percent"] == 8.0
    history = body.split("## Historique des cotes")[1].split("## Suivi")[0]
    assert history.count("- ") == 2


def test_settled_note_never_touched(vault, bet, now):
    path = vault.upsert_bet(bet, 1000, now).path
    path.write_text(path.read_text(encoding="utf-8").replace("statut: EN_ATTENTE", "statut: GAGNE"), encoding="utf-8")
    before = path.read_text(encoding="utf-8")
    res = vault.upsert_bet(replace(bet, betclic_odd=2.1), 1000, now)
    assert not res.updated
    assert path.read_text(encoding="utf-8") == before


def test_apply_settlement_updates_note(vault, bet, now):
    path = vault.upsert_bet(bet, 10, now).path
    record = {"id": bet.bet_id, "status": "GAGNE", "profit": 0.65, "final_score": "2-0", "odd": 1.65, "settled_odd": 1.65}
    assert vault.apply_settlement(record, now) == path
    meta, body = _read(path)
    assert (meta["statut"], meta["profit"], meta["score_final"]) == ("GAGNE", 0.65, "2-0")
    assert "Réglé automatiquement" in body and "+0.65 €" in body


def test_note_without_stats(vault, soccer_event, now):
    outcome = next(o for o in compare_event(soccer_event, now=now) if o.selection == "Plus de 2.5")
    opp = analyze(outcome, "Football", "Premier League", 1000, None, None)
    _, body = _read(vault.upsert_bet(opp, 1000, now).path)
    assert "Statistiques indisponibles" in body


def test_note_shows_stake_rule(vault, soccer_event, now, strong_home, weak_away):
    outcome = next(o for o in compare_event(soccer_event, now=now) if o.selection == "Arsenal")
    opp = analyze(outcome, "Football", "Premier League", 10.0, strong_home, weak_away)
    meta, body = _read(vault.upsert_bet(opp, 10.0, now).path)
    assert meta["mise_recommandee"] == 1.0 and meta["mise_percent"] == 10.0
    assert "Mise engagée : **1.00 €**" in body and "10 % du solde" in body


def test_derived_market_note_shows_minimum_odd(vault, soccer_event, now, strong_home, weak_away):
    from betclic_bot.derived import derive_outcomes

    h2h = compare_event(soccer_event, now=now)
    btts = next(o for o in derive_outcomes(soccer_event, h2h, strong_home, weak_away) if o.market == "btts")
    opp = analyze(btts, "Football", "Premier League", 100, strong_home, weak_away)
    if opp is None:  # selon le profil, l'issue peut être écartée : on force un cas retenu
        opp = analyze(replace(btts, betclic_odd=2.0, fair_prob=0.53, ev=0.53 * 2.0 - 1, min_odd=1.74),
                      "Football", "Premier League", 100, strong_home, weak_away)
    meta, body = _read(vault.upsert_bet(opp, 100, now).path)
    assert meta["cote_source"] == "estimee" and meta["type_marche"] == "btts"
    assert meta["cote_betclic"] == opp.min_odd
    assert "Cote minimale à exiger sur Betclic" in body and "non publiée via l'API" in body
