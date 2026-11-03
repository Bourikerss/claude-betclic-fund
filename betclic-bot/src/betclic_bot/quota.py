"""Gestion du quota mensuel The Odds API (500 crédits) et rotation des sports."""
from __future__ import annotations

import calendar
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from . import rules
from .odds_api import QuotaInfo

log = logging.getLogger(__name__)

NEVER_SCANNED_HOURS = 72.0
# Couverture = part des matchs renvoyés où Pinnacle ET Betclic sont présents (moyenne mobile exponentielle).
COVERAGE_SMOOTHING = 0.5  # poids de la dernière observation
COVERAGE_FLOOR = 0.1      # un sport sans Betclic garde 10 % de son score : il est retesté de temps en temps


class QuotaManager:
    def __init__(self, path: Path, monthly_credits: int = rules.MONTHLY_CREDITS, reserve: int = 30,
                 runs_per_day: int = 2, max_sports_per_run: int = 10,
                 cost_per_call: int = rules.COST_PER_ODDS_CALL):
        self.path = Path(path)
        self.monthly_credits = monthly_credits
        self.reserve = reserve
        self.runs_per_day = max(runs_per_day, 1)
        self.max_sports_per_run = max_sports_per_run
        self.cost_per_call = cost_per_call
        self.state = self._load()

    # --- persistance ---------------------------------------------------------
    def _load(self) -> dict:
        default = {"month": None, "used_local": 0, "api_remaining": None, "api_used": None, "last_scanned": {}, "coverage": {}}
        if self.path.exists():
            try:
                default.update(json.loads(self.path.read_text(encoding="utf-8")))
            except (ValueError, OSError):
                log.warning("État de quota illisible, réinitialisation : %s", self.path)
        return default

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.state, indent=2, ensure_ascii=False), encoding="utf-8")

    def _roll_month(self, now: datetime) -> None:
        month = now.strftime("%Y-%m")
        if self.state["month"] != month:
            self.state.update(month=month, used_local=0, api_remaining=None, api_used=None)

    # --- budget ---------------------------------------------------------------
    def remaining(self, now: datetime) -> int:
        """Crédits disponibles : min(en-tête API, budget mensuel local)."""
        self._roll_month(now)
        local = self.monthly_credits - int(self.state["used_local"])
        api = self.state["api_remaining"]
        return max(min(local, api) if api is not None else local, 0)

    def sports_budget(self, now: datetime) -> int:
        """Nombre de sports qu'on peut scanner pendant cette exécution."""
        available = self.remaining(now) - self.reserve
        if available < self.cost_per_call:
            return 0
        days_in_month = calendar.monthrange(now.year, now.month)[1]
        runs_left = (days_in_month - now.day + 1) * self.runs_per_day
        per_run = available / runs_left
        # Arrondi au plus proche : le budget est recalculé à chaque run, il s'auto-corrige.
        n = max(int(per_run / self.cost_per_call + 0.5), 1)
        return min(n, self.max_sports_per_run, available // self.cost_per_call)

    def update_from_api(self, info: QuotaInfo, now: datetime) -> None:
        self._roll_month(now)
        if info.remaining is not None:
            self.state["api_remaining"] = info.remaining
        if info.used is not None:
            self.state["api_used"] = info.used

    def record_call(self, sport_key: str, info: QuotaInfo, now: datetime) -> int:
        self._roll_month(now)
        cost = info.last_cost if info.last_cost is not None else self.cost_per_call
        self.state["used_local"] = int(self.state["used_local"]) + cost
        self.update_from_api(info, now)
        self.mark_scanned(sport_key, now)
        return cost

    def mark_scanned(self, sport_key: str, now: datetime) -> None:
        self.state["last_scanned"][sport_key] = now.isoformat()

    # --- couverture Betclic -------------------------------------------------------
    def record_coverage(self, sport_key: str, events: int, with_target: int) -> None:
        if events <= 0:
            return
        ratio = with_target / events
        prev = self.coverage(sport_key)
        value = ratio if prev is None else COVERAGE_SMOOTHING * ratio + (1 - COVERAGE_SMOOTHING) * prev
        self.state["coverage"][sport_key] = round(value, 4)

    def coverage(self, sport_key: str) -> Optional[float]:
        return self.state["coverage"].get(sport_key)

    def coverage_factor(self, sport_key: str) -> float:
        """1.0 tant que la couverture est inconnue, sinon max(couverture, plancher)."""
        cov = self.coverage(sport_key)
        return 1.0 if cov is None else max(cov, COVERAGE_FLOOR)

    # --- rotation ---------------------------------------------------------------
    def hours_since_scan(self, sport_key: str, now: datetime) -> float:
        last = self.state["last_scanned"].get(sport_key)
        if not last:
            return NEVER_SCANNED_HOURS
        delta = now - datetime.fromisoformat(last)
        return min(max(delta.total_seconds() / 3600, 0.0), NEVER_SCANNED_HOURS)

    def rank(self, weights: Dict[str, float], now: datetime) -> List[str]:
        """Trie les sports par score = poids × couverture Betclic × heures depuis le dernier scan."""
        return sorted(
            weights,
            key=lambda k: (weights[k] * self.coverage_factor(k) * self.hours_since_scan(k, now), weights[k]),
            reverse=True,
        )

    def summary(self, now: datetime) -> Dict[str, Optional[int]]:
        return {
            "mois": self.state["month"] if self.state["month"] else now.strftime("%Y-%m"),
            "credits_restants": self.remaining(now),
            "credits_utilises_mois": int(self.state["used_local"]),
            "api_remaining": self.state["api_remaining"],
            "sports_par_run": self.sports_budget(now),
        }
