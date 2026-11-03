"""Règlement automatique des paris EN_ATTENTE à partir des scores finaux ESPN.

Pour chaque sélection dont le match est terminé, on lit le score sur le scoreboard ESPN de la
compétition (`/apis/site/v2/sports/{sport}/{league}/scoreboard?dates=AAAAMMJJ`) et on évalue le
marché. Un pari simple suit sa sélection ; un combiné est perdu dès qu'une sélection est perdue,
gagné quand toutes sont gagnées (une sélection remboursée compte pour une cote de 1).
Match reporté ou annulé : sélection remboursée. Match introuvable 3 jours après : remboursé.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from math import prod
from typing import Dict, List, Optional, Tuple

from .ledger import LOST, PENDING, VOID, WON, Ledger, parse_iso
from .stats_client import BASE, ESPN_LEAGUES, StatsClient, name_similarity

log = logging.getLogger(__name__)

SCOREBOARD_URL = BASE + "/site/v2/sports/{sport}/{league}/scoreboard?dates={date}"
FINAL = {"STATUS_FULL_TIME", "STATUS_FINAL", "STATUS_FINAL_AET", "STATUS_FINAL_PEN", "STATUS_FINAL_OT"}
CANCELLED = {"STATUS_POSTPONED", "STATUS_CANCELED", "STATUS_CANCELLED", "STATUS_ABANDONED", "STATUS_FORFEIT"}
MATCH_DURATION = {"soccer": timedelta(hours=2, minutes=15), "basketball": timedelta(hours=3)}
GIVE_UP_AFTER = timedelta(days=3)


@dataclass
class SettleReport:
    settled: List[dict] = field(default_factory=list)   # paris réglés pendant ce run
    still_open: int = 0

    @property
    def won(self) -> int:
        return sum(b["status"] == WON for b in self.settled)

    @property
    def lost(self) -> int:
        return sum(b["status"] == LOST for b in self.settled)

    @property
    def profit(self) -> float:
        return round(sum(b["profit"] for b in self.settled), 2)


def evaluate_leg(market: str, outcome: str, point: Optional[float], home: str, away: str,
                 home_score: float, away_score: float) -> str:
    """Résultat d'une sélection d'après le score final (temps réglementaire pour le football)."""
    diff, total = home_score - away_score, home_score + away_score
    if market == "h2h":
        winner = home if diff > 0 else away if diff < 0 else "Draw"
        return WON if outcome == winner else LOST
    if market == "double_chance":
        ok = {"1X": diff >= 0, "X2": diff <= 0, "12": diff != 0}[outcome]
        return WON if ok else LOST
    if market == "dnb":
        if diff == 0:
            return VOID
        return WON if (outcome == home) == (diff > 0) else LOST
    if market == "btts":
        both = home_score > 0 and away_score > 0
        return WON if both == (outcome == "Yes") else LOST
    if market == "totals":
        if total == point:
            return VOID
        return WON if (total > point) == (outcome == "Over") else LOST
    if market == "team_totals":
        team, side = outcome.rsplit(" ", 1)
        goals = home_score if team == home else away_score
        if goals == point:
            return VOID
        return WON if (goals > point) == (side == "Over") else LOST
    if market == "spreads":
        margin = (diff if outcome == home else -diff) + point
        return VOID if margin == 0 else WON if margin > 0 else LOST
    raise ValueError(f"Marché inconnu : {market}")


def combine(statuses: List[str]) -> str:
    if LOST in statuses:
        return LOST
    if PENDING in statuses:
        return PENDING
    return VOID if all(s == VOID for s in statuses) else WON


class AutoSettler:
    def __init__(self, stats_client: StatsClient):
        self.stats = stats_client

    def _scoreboard(self, sport: str, league: str, day: datetime) -> List[dict]:
        url = SCOREBOARD_URL.format(sport=sport, league=league, date=day.strftime("%Y%m%d"))
        data = self.stats.get_json(url, max_age=3600) or {}  # scores frais : cache d'1 h seulement
        return data.get("events", [])

    def find_result(self, leg: dict) -> Optional[Tuple[str, float, float]]:
        """(statut ESPN, buts domicile, buts extérieur) du match d'une sélection, ou None."""
        if leg["sport_key"] not in ESPN_LEAGUES:
            return None
        sport, league = ESPN_LEAGUES[leg["sport_key"]]
        kickoff = parse_iso(leg["kickoff"])
        # ESPN date les matchs à l'heure de la côte Est des États-Unis : on regarde J et J−1.
        for day in (kickoff, kickoff - timedelta(days=1)):
            for event in self._scoreboard(sport, league, day):
                comp = (event.get("competitions") or [{}])[0]
                sides = {c.get("homeAway"): c for c in comp.get("competitors", [])}
                if "home" not in sides or "away" not in sides:
                    continue
                h, a = sides["home"], sides["away"]
                if name_similarity(leg["home"], h["team"]["displayName"]) < 0.75 \
                        or name_similarity(leg["away"], a["team"]["displayName"]) < 0.75:
                    continue
                status = comp.get("status", {}).get("type", {}).get("name") \
                    or event.get("status", {}).get("type", {}).get("name", "")
                try:
                    return status, float(h.get("score") or 0), float(a.get("score") or 0)
                except (TypeError, ValueError):
                    return status, 0.0, 0.0
        return None

    def settle_leg(self, leg: dict, now: datetime) -> str:
        if leg.get("status", PENDING) != PENDING:
            return leg["status"]
        kickoff = parse_iso(leg["kickoff"])
        sport = ESPN_LEAGUES.get(leg["sport_key"], ("soccer",))[0]
        if now < kickoff + MATCH_DURATION.get(sport, timedelta(hours=3)):
            return PENDING
        found = self.find_result(leg)
        if found is None:
            if now > kickoff + GIVE_UP_AFTER:
                leg.update(status=VOID, final_score="match introuvable")
                return VOID
            return PENDING
        status, hs, as_ = found
        if status in CANCELLED:
            leg.update(status=VOID, final_score="reporté/annulé")
        elif status in FINAL:
            leg.update(status=evaluate_leg(leg["market"], leg["outcome_name"], leg.get("point"),
                                           leg["home"], leg["away"], hs, as_),
                       final_score=f"{hs:g}-{as_:g}")
        return leg.get("status", PENDING)

    def run(self, ledger: Ledger, now: Optional[datetime] = None) -> SettleReport:
        now = now or datetime.now(timezone.utc)
        report = SettleReport()
        for bet in ledger.open_bets():
            statuses = [self.settle_leg(leg, now) for leg in bet["legs"]]
            result = combine(statuses)
            if result == PENDING:
                report.still_open += 1
                continue
            odd = prod(l["odd"] for l in bet["legs"] if l["status"] == WON) if result == WON else None
            scores = " · ".join(l.get("final_score") or "?" for l in bet["legs"])
            report.settled.append(ledger.settle(bet["id"], result, now, scores, odd))
        return report
