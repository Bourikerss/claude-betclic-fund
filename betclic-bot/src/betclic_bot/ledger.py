"""Grand livre du « Challenge 10 € de Claude » (paper trading) : `data/ledger.json`.

Fonctionne comme un relevé de compte :
- `operations` : chaque mouvement (dépôt initial, mise débitée, gain ou remboursement crédité, perte)
  avec le solde disponible après l'opération ;
- `bets` : l'historique complet des paris (simples et combinés), chacun décrit par ses sélections (`legs`).

Le solde disponible (cash) baisse quand une mise est engagée ; le capital réalisé
(`equity` = solde initial + profits des paris réglés) sert à la courbe et au drawdown.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from . import rules

PENDING = rules.STATUT_EN_ATTENTE
WON, LOST, VOID = "GAGNE", "PERDU", "REMBOURSE"


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


@dataclass(frozen=True)
class Metrics:
    initial: float
    balance: float          # solde disponible (cash)
    equity: float           # capital réalisé : initial + profits réglés
    exposure: float         # mises engagées sur des paris en cours
    profit: float
    roi: float              # profit / capital initial
    yield_: float           # profit / total misé sur les paris réglés
    winrate: Optional[float]
    won: int
    lost: int
    void: int
    pending: int
    staked_settled: float
    max_drawdown: float     # en € (baisse maximale depuis un sommet du capital réalisé)
    max_drawdown_pct: float


class Ledger:
    def __init__(self, path: Path, initial: float = rules.INITIAL_BANKROLL, now: Optional[datetime] = None):
        self.path = Path(path)
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            created = iso(now or datetime.now(timezone.utc))
            self.data = {
                "initial": round(initial, 2),
                "created_at": created,
                "operations": [{"date": created, "type": "DEPOT", "label": "Capital de départ",
                                "bet_id": None, "amount": round(initial, 2), "balance": round(initial, 2)}],
                "bets": {},
            }

    # --- persistance -----------------------------------------------------------------
    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)

    # --- lecture ------------------------------------------------------------------------
    @property
    def initial(self) -> float:
        return float(self.data["initial"])

    @property
    def operations(self) -> List[dict]:
        return self.data["operations"]

    @property
    def bets(self) -> Dict[str, dict]:
        return self.data["bets"]

    @property
    def balance(self) -> float:
        return round(float(self.operations[-1]["balance"]), 2)

    def open_bets(self) -> List[dict]:
        return [b for b in self.bets.values() if b["status"] == PENDING]

    def has_bet(self, bet_id: str) -> bool:
        return bet_id in self.bets

    def open_events(self) -> set:
        return {leg["event_id"] for b in self.open_bets() for leg in b["legs"]}

    def staked_on(self, day: str, tz: str = "Europe/Paris") -> float:
        """Total misé sur les paris placés le jour local `day` (AAAA-MM-JJ)."""
        zone = ZoneInfo(tz)
        return round(sum(b["stake"] for b in self.bets.values()
                         if parse_iso(b["placed_at"]).astimezone(zone).strftime("%Y-%m-%d") == day), 2)

    def daily_budget(self, now: datetime, tz: str = "Europe/Paris") -> float:
        """Montant encore engageable aujourd'hui : 35 % du solde disponible en début de journée."""
        day = now.astimezone(ZoneInfo(tz)).strftime("%Y-%m-%d")
        already = self.staked_on(day, tz)
        start_of_day = self.balance + already
        return round(max(0.0, rules.DAILY_EXPOSURE_MAX * start_of_day - already), 2)

    # --- écriture -----------------------------------------------------------------------
    def _operation(self, now: datetime, kind: str, label: str, bet_id: Optional[str], amount: float) -> dict:
        op = {"date": iso(now), "type": kind, "label": label, "bet_id": bet_id,
              "amount": round(amount, 2), "balance": round(self.balance + amount, 2)}
        self.operations.append(op)
        return op

    def place(self, bet: dict, stake: float, now: datetime) -> dict:
        """Engage une mise : débit du solde et ajout du pari (statut EN_ATTENTE)."""
        if bet["id"] in self.bets:
            raise ValueError(f"Pari déjà engagé : {bet['id']}")
        stake = round(stake, 2)
        if stake <= 0 or stake > self.balance + 1e-9:
            raise ValueError(f"Mise impossible ({stake} €, solde {self.balance} €)")
        record = dict(bet, stake=stake, placed_at=iso(now), status=PENDING, payout=None, profit=None,
                      settled_at=None, final_score=None,
                      potential_payout=round(stake * bet["odd"], 2))
        self.bets[bet["id"]] = record
        self._operation(now, "MISE", f"Mise · {bet['label']}", bet["id"], -stake)
        return record

    def settle(self, bet_id: str, status: str, now: datetime, final_score: Optional[str] = None,
               settled_odd: Optional[float] = None) -> dict:
        """Règle un pari : crédit du gain (cote × mise) ou du remboursement ; une perte ne crédite rien."""
        bet = self.bets[bet_id]
        if bet["status"] != PENDING:
            return bet
        odd = settled_odd if settled_odd is not None else bet["odd"]
        payout = {WON: round(bet["stake"] * odd, 2), VOID: bet["stake"], LOST: 0.0}[status]
        bet.update(status=status, payout=payout, profit=round(payout - bet["stake"], 2),
                   settled_at=iso(now), final_score=final_score, settled_odd=round(odd, 3))
        kind = {WON: "GAIN", VOID: "REMBOURSEMENT", LOST: "PERTE"}[status]
        self._operation(now, kind, f"{kind.capitalize()} · {bet['label']}", bet_id, payout)
        return bet

    # --- indicateurs --------------------------------------------------------------------
    def settled(self) -> List[dict]:
        done = [b for b in self.bets.values() if b["status"] != PENDING]
        return sorted(done, key=lambda b: (b["settled_at"], b["placed_at"]))

    def equity_series(self) -> List[Tuple[str, float, Optional[dict]]]:
        """(date, capital réalisé, pari réglé) : point de départ puis un point par pari réglé."""
        points: List[Tuple[str, float, Optional[dict]]] = [(self.data["created_at"], self.initial, None)]
        equity = self.initial
        for bet in self.settled():
            equity = round(equity + bet["profit"], 2)
            points.append((bet["settled_at"], equity, bet))
        return points

    def metrics(self) -> Metrics:
        settled = self.settled()
        won = sum(b["status"] == WON for b in settled)
        lost = sum(b["status"] == LOST for b in settled)
        void = sum(b["status"] == VOID for b in settled)
        profit = round(sum(b["profit"] for b in settled), 2)
        staked = round(sum(b["stake"] for b in settled if b["status"] != VOID), 2)
        peak, max_dd, max_dd_pct = self.initial, 0.0, 0.0
        for _, equity, _ in self.equity_series():
            peak = max(peak, equity)
            if peak - equity > max_dd:
                max_dd, max_dd_pct = peak - equity, (peak - equity) / peak
        open_bets = self.open_bets()
        return Metrics(
            initial=self.initial, balance=self.balance, equity=round(self.initial + profit, 2),
            exposure=round(sum(b["stake"] for b in open_bets), 2), profit=profit,
            roi=profit / self.initial, yield_=profit / staked if staked else 0.0,
            winrate=won / (won + lost) if won + lost else None,
            won=won, lost=lost, void=void, pending=len(open_bets), staked_settled=staked,
            max_drawdown=round(max_dd, 2), max_drawdown_pct=max_dd_pct,
        )
