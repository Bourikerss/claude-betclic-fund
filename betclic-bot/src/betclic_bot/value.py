"""Expected Value et mise selon le profil de risque.

Voir « Expected Value (EV).md » et « Profils de risque.md » dans le coffre.
"""
from __future__ import annotations

from typing import Tuple

from . import rules


def expected_value(prob: float, odd: float) -> float:
    """EV par euro misé : p × c − 1."""
    return prob * odd - 1.0


def profile_stake(profile: str, available: float) -> Tuple[float, float, float]:
    """Retourne (mise en €, % du profil, mise théorique) — CLAUDE.md §4.

    Mise = solde actuel × % du profil (Safe 10 %, Sweet Spot 7 %, Audacieux et Combiné 5 %),
    avec un plancher absolu de `STAKE_MIN` (0,50 €) : proportionnelle, sans plafond.
    """
    pct = rules.STAKE_PCT[profile]
    theoretical = round(available * pct, 2)
    return max(theoretical, rules.STAKE_MIN), pct, theoretical
