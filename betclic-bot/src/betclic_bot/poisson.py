"""Modèle de Poisson (forces offensives/défensives) calibré sur les probabilités Pinnacle.

On cherche les buts attendus λ_dom et λ_ext tels que la loi de Poisson reproduise au mieux :
- les probabilités 1N2 sans marge de Pinnacle (h2h),
- la probabilité « Plus de X buts » de Pinnacle (totals) si elle est disponible,
- sinon un total attendu tiré des moyennes ESPN (a priori faible).
On en déduit ensuite la probabilité juste de tous les marchés internes au match.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import exp, factorial
from typing import List, Optional, Tuple

MAX_GOALS = 10
_GRID = [round(0.1 * i, 2) for i in range(1, 46)]  # 0.1 → 4.5 buts


def _pmf(lam: float) -> List[float]:
    return [exp(-lam) * lam ** k / factorial(k) for k in range(MAX_GOALS + 1)]


@dataclass(frozen=True)
class ScoreModel:
    lambda_home: float
    lambda_away: float

    @property
    def matrix(self) -> List[List[float]]:
        ph, pa = _pmf(self.lambda_home), _pmf(self.lambda_away)
        return [[ph[i] * pa[j] for j in range(MAX_GOALS + 1)] for i in range(MAX_GOALS + 1)]

    def _sum(self, cond) -> float:
        m = self.matrix
        total = sum(sum(row) for row in m)  # ≈ 1, la troncature à 10 buts est négligeable
        return sum(m[i][j] for i in range(MAX_GOALS + 1) for j in range(MAX_GOALS + 1) if cond(i, j)) / total

    # --- 1N2 ---------------------------------------------------------------------------
    def h2h(self) -> Tuple[float, float, float]:
        return self._sum(lambda i, j: i > j), self._sum(lambda i, j: i == j), self._sum(lambda i, j: i < j)

    # --- totaux ---------------------------------------------------------------------------
    def over(self, line: float) -> float:
        return self._sum(lambda i, j: i + j > line)

    def team_over(self, home: bool, line: float) -> float:
        return self._sum(lambda i, j: (i if home else j) > line)

    def btts(self) -> float:
        return self._sum(lambda i, j: i > 0 and j > 0)

    def margin_at_least(self, home: bool, goals: int) -> float:
        """Probabilité que l'équipe gagne par `goals` buts d'écart ou plus (handicap −(goals − 0.5))."""
        return self._sum(lambda i, j: ((i - j) if home else (j - i)) >= goals)


def _error(model: ScoreModel, target: Tuple[float, float, float], over: Optional[Tuple[float, float]],
           prior_total: Optional[float]) -> float:
    p1, px, p2 = model.h2h()
    err = (p1 - target[0]) ** 2 + (px - target[1]) ** 2 + (p2 - target[2]) ** 2
    if over is not None:
        line, p_over = over
        err += 2 * (model.over(line) - p_over) ** 2  # les totals Pinnacle fixent le niveau de buts
    elif prior_total is not None:
        err += 0.002 * (model.lambda_home + model.lambda_away - prior_total) ** 2
    return err


def fit(h2h_fair: Tuple[float, float, float], over: Optional[Tuple[float, float]] = None,
        prior_total: Optional[float] = None) -> ScoreModel:
    """Ajuste (λ_dom, λ_ext) : grille grossière (pas 0.1) puis affinage (pas 0.01)."""
    best = min(((_error(ScoreModel(h, a), h2h_fair, over, prior_total), h, a) for h in _GRID for a in _GRID))
    _, h0, a0 = best
    fine = [round(x * 0.01, 2) for x in range(-10, 11)]
    best = min(((_error(ScoreModel(h0 + dh, a0 + da), h2h_fair, over, prior_total), h0 + dh, a0 + da)
                for dh in fine for da in fine if h0 + dh > 0.05 and a0 + da > 0.05))
    return ScoreModel(round(best[1], 2), round(best[2], 2))
