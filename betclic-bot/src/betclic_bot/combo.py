"""Combiné du jour : 2 à 3 sélections solides sur des matchs différents, cote totale 1.70 – 2.40."""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from math import prod
from typing import Iterable, List, Optional, Sequence

from . import rules
from .detector import ComparedOutcome


@dataclass(frozen=True)
class ComboLeg:
    outcome: ComparedOutcome
    convergence: float
    headline: str
    sport: str
    ligue: str

    @property
    def odd(self) -> float:
        """Cote engagée : vraie cote Betclic, ou cote minimale à exiger pour un marché dérivé."""
        o = self.outcome
        return o.min_odd if o.estimated and o.min_odd else o.betclic_odd


@dataclass(frozen=True)
class Combo:
    legs: Sequence[ComboLeg]

    @property
    def odd(self) -> float:
        return round(prod(leg.odd for leg in self.legs), 2)

    @property
    def fair_prob(self) -> float:
        return prod(leg.outcome.fair_prob for leg in self.legs)

    @property
    def ev(self) -> float:
        return self.fair_prob * self.odd - 1

    @property
    def convergence(self) -> float:
        return sum(leg.convergence for leg in self.legs) / len(self.legs)


def is_leg_candidate(outcome: ComparedOutcome, convergence: Optional[float]) -> bool:
    odd = outcome.min_odd if outcome.estimated and outcome.min_odd else outcome.betclic_odd
    return (rules.COMBO_LEG_MIN_ODD <= odd <= rules.COMBO_LEG_MAX_ODD
            and outcome.fair_prob >= rules.COMBO_LEG_MIN_PROB
            and outcome.ev >= rules.MIN_EV - 1e-9
            and convergence is not None and convergence >= rules.COMBO_LEG_MIN_STATS)


def best_combo(legs: Iterable[ComboLeg], exclude_events: Iterable[str] = (), pool: int = 20) -> Optional[Combo]:
    """Meilleur combiné : sélections les plus convergentes, puis probabilité combinée la plus haute."""
    excluded = set(exclude_events)
    # Une seule sélection par match : la plus convergente.
    best_by_event = {}
    for leg in sorted(legs, key=lambda l: (l.convergence, l.outcome.fair_prob), reverse=True):
        if leg.outcome.event_id not in excluded:
            best_by_event.setdefault(leg.outcome.event_id, leg)
    candidates: List[ComboLeg] = list(best_by_event.values())[:pool]
    best: Optional[Combo] = None
    for size in range(rules.COMBO_MIN_LEGS, rules.COMBO_MAX_LEGS + 1):
        for group in combinations(candidates, size):
            combo = Combo(group)
            if not rules.COMBO_MIN_ODD <= combo.odd <= rules.COMBO_MAX_ODD:
                continue
            if best is None or (combo.convergence, combo.fair_prob) > (best.convergence, best.fair_prob):
                best = combo
    return best
