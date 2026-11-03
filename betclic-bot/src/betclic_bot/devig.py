"""Retrait de la marge (dé-vigging) des cotes Pinnacle.

Voir « 01 - Architecture & Stratégie/Dé-vigging Pinnacle.md ».
"""
from __future__ import annotations

from typing import List, Sequence

METHODS = ("multiplicative", "power")


def _validate(odds: Sequence[float]) -> None:
    if len(odds) < 2:
        raise ValueError("Il faut au moins deux issues pour retirer la marge")
    if any(o <= 1.0 for o in odds):
        raise ValueError(f"Cotes décimales invalides : {list(odds)}")


def overround(odds: Sequence[float]) -> float:
    """Somme des probabilités implicites (1.0 = marché sans marge)."""
    _validate(odds)
    return sum(1.0 / o for o in odds)


def devig_multiplicative(odds: Sequence[float]) -> List[float]:
    """Méthode proportionnelle : p_i = (1/c_i) / Σ(1/c_j)."""
    total = overround(odds)
    return [(1.0 / o) / total for o in odds]


def devig_power(odds: Sequence[float], tol: float = 1e-12, max_iter: int = 200) -> List[float]:
    """Méthode « power » : on cherche k tel que Σ(1/c_i)^k = 1.

    Attribue davantage de marge aux outsiders (biais favori/outsider).
    """
    _validate(odds)
    implied = [1.0 / o for o in odds]
    lo, hi = 0.01, 20.0
    k = 1.0
    for _ in range(max_iter):
        k = (lo + hi) / 2
        s = sum(p ** k for p in implied)
        if abs(s - 1.0) < tol:
            break
        # Σ p^k décroît avec k (p < 1)
        if s > 1.0:
            lo = k
        else:
            hi = k
    probs = [p ** k for p in implied]
    total = sum(probs)
    return [p / total for p in probs]


def fair_probabilities(odds: Sequence[float], method: str = "multiplicative") -> List[float]:
    if method == "multiplicative":
        return devig_multiplicative(odds)
    if method == "power":
        return devig_power(odds)
    raise ValueError(f"Méthode de dé-vigging inconnue : {method!r} (attendu : {METHODS})")
