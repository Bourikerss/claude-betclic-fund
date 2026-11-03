"""Gestion du « Fonds Claude » (paper trading, 10 € de départ) : sélection du jour, mises, engagement.

Chaque jour : 2 à 4 paris simples variés (Top du scan, CLAUDE.md §3) + 1 Combiné du jour
(ou, à défaut, un pari Fun / Audacieux). Mise = solde actuel × % du profil, plancher 0,50 €,
sans jamais engager plus de 35 % du solde disponible sur une même journée.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import List, Optional
from zoneinfo import ZoneInfo

from . import rules
from .analyzer import select_top
from .combo import Combo, best_combo
from .ledger import PENDING, Ledger, iso
from .models import MARKET_LABELS, Opportunity
from .value import profile_stake

log = logging.getLogger(__name__)


@dataclass
class Position:
    record: dict                       # pari tel qu'inscrit au grand livre
    opportunity: Optional[Opportunity] = None
    combo: Optional[Combo] = None


@dataclass
class DailyPlan:
    base_balance: float
    budget: float
    singles: List[Position] = field(default_factory=list)
    combo: Optional[Position] = None   # Combiné du jour, ou pari Fun à défaut
    skipped: List[str] = field(default_factory=list)

    @property
    def positions(self) -> List[Position]:
        return self.singles + ([self.combo] if self.combo else [])

    @property
    def total_staked(self) -> float:
        return round(sum(p.record["stake"] for p in self.positions), 2)


def leg_from_opportunity(opp: Opportunity) -> dict:
    return {
        "event_id": opp.event_id, "sport_key": opp.sport_key, "sport": opp.sport, "competition": opp.ligue,
        "home": opp.home_team, "away": opp.away_team, "match": opp.match, "kickoff": iso(opp.commence_time),
        "market": opp.market, "market_label": opp.market_label, "outcome_name": opp.outcome_name,
        "point": opp.point, "selection": opp.selection, "odd": opp.odd_to_take, "estimated": opp.estimated,
        "status": PENDING, "final_score": None,
    }


def single_record(opp: Opportunity, kind: str = "SIMPLE") -> dict:
    return {
        "id": opp.bet_id, "kind": kind, "label": f"{opp.match} · {opp.selection}",
        "sport": opp.sport, "competition": opp.ligue, "match": opp.match, "kickoff": iso(opp.commence_time),
        "market": opp.market, "market_label": opp.market_label, "selection": opp.selection,
        "odd": opp.odd_to_take, "estimated": opp.estimated, "profile": opp.profile, "score": opp.score,
        "fair_prob": round(opp.fair_prob, 4), "ev": round(opp.ev, 4), "headline": opp.headline,
        "legs": [leg_from_opportunity(opp)],
    }


def combo_record(combo: Combo, now: datetime, tz: str) -> dict:
    day = now.astimezone(ZoneInfo(tz)).strftime("%Y%m%d")
    legs = []
    for leg in combo.legs:
        o = leg.outcome
        legs.append({
            "event_id": o.event_id, "sport_key": o.sport_key, "sport": leg.sport, "competition": leg.ligue,
            "home": o.home_team, "away": o.away_team, "match": f"{o.home_team} vs {o.away_team}",
            "kickoff": iso(o.commence_time), "market": o.market, "market_label": MARKET_LABELS.get(o.market, o.market),
            "outcome_name": o.outcome_name, "point": o.point, "selection": o.selection, "odd": leg.odd,
            "estimated": o.estimated, "headline": leg.headline, "status": PENDING, "final_score": None,
        })
    competitions = sorted({l["competition"] for l in legs})
    return {
        "id": f"combo_{day}", "kind": "COMBINE", "label": f"Combiné du jour · {len(legs)} sélections",
        "sport": "Multi", "competition": " · ".join(competitions), "match": " + ".join(l["match"] for l in legs),
        "kickoff": max(l["kickoff"] for l in legs), "market": "combo", "market_label": "Combiné",
        "selection": " + ".join(l["selection"] for l in legs), "odd": combo.odd, "estimated": any(l["estimated"] for l in legs),
        "profile": rules.PROFILE_COMBINE, "score": int(round(combo.convergence * 100)),
        "fair_prob": round(combo.fair_prob, 4), "ev": round(combo.ev, 4),
        "headline": f"{len(legs)} sélections, {combo.fair_prob * 100:.0f} % de réussite combinée selon Pinnacle",
        "legs": legs,
    }


def _fit_stake(stake: float, remaining: float, cash: float) -> Optional[float]:
    """Mise réellement engageable : réduite au plafond du jour si besoin, jamais sous 0,50 €."""
    stake = round(min(stake, remaining, cash), 2)
    return stake if stake >= rules.STAKE_MIN - 1e-9 else None


def plan_day(candidates: List[Opportunity], combo_legs, ledger: Ledger, now: datetime,
             tz: str = "Europe/Paris") -> DailyPlan:
    """Choisit et dimensionne les paris du jour, sans rien engager."""
    base = ledger.balance  # solde actuel, lu une fois en début de run
    plan = DailyPlan(base_balance=base, budget=ledger.daily_budget(now, tz))
    remaining, cash = plan.budget, base
    open_events = ledger.open_events()
    pool = [o for o in candidates if o.event_id not in open_events and not ledger.has_bet(o.bet_id)]

    def sized(opp: Opportunity, profile: str) -> Optional[Opportunity]:
        theoretical_stake, pct, theoretical = profile_stake(profile, base)
        stake = _fit_stake(theoretical_stake, remaining, cash)
        if stake is None:
            plan.skipped.append(f"{opp.match} · {opp.selection} : plafond de 35 % atteint")
            return None
        return replace(opp, stake=stake, stake_pct=pct, stake_theoretical=theoretical)

    for opp in select_top(pool, rules.MAX_PICKS_PER_SCAN):
        opp = sized(opp, opp.profile)
        if opp is None:
            continue
        remaining, cash = round(remaining - opp.stake, 2), round(cash - opp.stake, 2)
        plan.singles.append(Position(single_record(opp) | {"stake": opp.stake}, opp))

    used = open_events | {p.record["legs"][0]["event_id"] for p in plan.singles}
    combo = best_combo(combo_legs, exclude_events=used)
    if combo and not ledger.has_bet(combo_record(combo, now, tz)["id"]):
        wanted = profile_stake(rules.PROFILE_COMBINE, base)[0]
        stake = _fit_stake(wanted, remaining, cash)
        # Le Combiné du jour prime sur le pari simple au plus faible score si le plafond de 35 % bloque,
        # en gardant au moins MIN_PICKS_PER_SCAN paris simples.
        while stake is None and len(plan.singles) > rules.MIN_PICKS_PER_SCAN:
            dropped = min(plan.singles, key=lambda pos: pos.record["score"])
            plan.singles.remove(dropped)
            remaining = round(remaining + dropped.record["stake"], 2)
            cash = round(cash + dropped.record["stake"], 2)
            plan.skipped.append(f"{dropped.record['label']} : remplacé par le Combiné du jour (plafond de 35 %)")
            stake = _fit_stake(wanted, remaining, cash)
        if stake is not None:
            plan.combo = Position(combo_record(combo, now, tz) | {"stake": stake}, combo=combo)
    elif not combo:
        # Pas de combiné possible : un pari Fun / Audacieux à belle cote, sur un autre match.
        fun = next((o for o in sorted(pool, key=lambda o: o.score, reverse=True)
                    if o.profile == rules.PROFILE_AUDACIEUX and o.event_id not in used), None)
        fun = sized(fun, rules.PROFILE_AUDACIEUX) if fun else None
        if fun:
            plan.combo = Position(single_record(fun, kind="FUN") | {"stake": fun.stake}, fun)
    return plan


def commit_plan(plan: DailyPlan, ledger: Ledger, vault, now: datetime) -> None:
    """Engage les mises au grand livre et écrit les fiches Obsidian."""
    for position in plan.positions:
        record = dict(position.record)
        stake = record.pop("stake")
        ledger.place(record, stake, now)
        if position.opportunity is not None:
            vault.upsert_bet(position.opportunity, plan.base_balance, now)
        else:
            vault.write_combo(ledger.bets[record["id"]], plan.base_balance, now)
    ledger.save()
