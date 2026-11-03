"""Appariement des marchés Pinnacle (fair) ↔ Betclic, issue par issue."""
from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from . import rules
from .devig import fair_probabilities
from .value import expected_value

log = logging.getLogger(__name__)

LineKey = Optional[float]


@dataclass
class DetectionStats:
    """Diagnostic d'un scan : pourquoi des issues sont (ou ne sont pas) retenues."""
    events: int = 0
    events_with_both: int = 0
    compared: Counter = field(default_factory=Counter)    # lignes comparées, par marché
    skipped: Counter = field(default_factory=Counter)     # matchs/lignes non comparables, par raison
    rejections: Counter = field(default_factory=Counter)  # issues écartées par l'analyste, par raison
    candidates: Counter = field(default_factory=Counter)  # issues éligibles, par profil
    # (EV, profil, libellé) des issues dans un profil mais écartées pour EV trop basse
    near_misses: List[Tuple[float, str, str]] = field(default_factory=list)
    teams_with_stats: int = 0
    derived: int = 0  # issues dérivées (double chance, DNB, BTTS, Over/Under, handicap) analysées
    teams_looked_up: int = 0


@dataclass(frozen=True)
class ComparedOutcome:
    """Une issue Betclic mise en regard de sa probabilité réelle Pinnacle."""
    event_id: str
    sport_key: str
    home_team: str
    away_team: str
    commence_time: datetime  # UTC
    market: str
    outcome_name: str
    point: Optional[float]
    selection: str
    betclic_odd: float
    pinnacle_odd: float
    fair_prob: float
    ev: float
    pinnacle_overround: float
    betclic_overround: float
    best_in_grid: bool  # meilleur rapport cote Betclic / cote juste parmi les issues de la ligne
    # Marchés dérivés (modèle de Poisson) : Betclic ne publie pas la cote via l'API.
    # `betclic_odd` est alors une estimation (cote juste ÷ marge 1N2 Betclic du match)
    # et `min_odd` la cote minimale à exiger sur Betclic.
    estimated: bool = False
    min_odd: Optional[float] = None


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _find_market(bookmaker: dict, key: str) -> Optional[dict]:
    for market in bookmaker.get("markets", []):
        if market.get("key") == key:
            return market
    return None


def _line_key(market_key: str, outcome: dict, home: str) -> LineKey:
    """Identifie la « ligne » d'une issue pour apparier Pinnacle et Betclic.

    - h2h : une seule ligne.
    - totals : le seuil (2.5, 215.5…).
    - spreads : le handicap exprimé du point de vue de l'équipe à domicile,
      pour que « Home -1.5 » et « Away +1.5 » tombent sur la même ligne.
    """
    if market_key == "h2h":
        return None
    point = float(outcome["point"])
    if market_key == "spreads" and outcome["name"] != home:
        point = -point
    return round(point, 2)


def group_outcomes(market_key: str, outcomes: List[dict], home: str) -> Dict[LineKey, Dict[str, dict]]:
    groups: Dict[LineKey, Dict[str, dict]] = {}
    for outcome in outcomes:
        if market_key != "h2h" and outcome.get("point") is None:
            continue
        groups.setdefault(_line_key(market_key, outcome, home), {})[outcome["name"]] = outcome
    return groups


def _is_complete(market_key: str, names: set, home: str, away: str) -> bool:
    if market_key == "totals":
        return names == {"Over", "Under"}
    if market_key == "spreads":
        return names == {home, away}
    return {home, away} <= names and names <= {home, away, "Draw"}


def selection_label(market_key: str, name: str, point: Optional[float]) -> str:
    if market_key == "totals":
        return f"{'Plus' if name == 'Over' else 'Moins'} de {point:g}"
    if market_key == "spreads":
        return f"{name} {point:+g}"
    return "Match nul" if name == "Draw" else name


def pinnacle_fair_lines(event: dict, market_key: str, devig_method: str = "multiplicative"
                        ) -> Dict[LineKey, Dict[str, float]]:
    """Probabilités sans marge de Pinnacle seul, par ligne (sert à calibrer le modèle de Poisson)."""
    sharp = next((b for b in event.get("bookmakers", []) if b.get("key") == rules.SHARP_BOOK), None)
    market = _find_market(sharp, market_key) if sharp else None
    if not market:
        return {}
    home, away = event["home_team"], event["away_team"]
    lines: Dict[LineKey, Dict[str, float]] = {}
    for line, outcomes in group_outcomes(market_key, market["outcomes"], home).items():
        names = sorted(outcomes)
        odds = [float(outcomes[n]["price"]) for n in names]
        if not _is_complete(market_key, set(names), home, away) or any(o <= 1.0 for o in odds) \
                or sum(1 / o for o in odds) > rules.MAX_PINNACLE_OVERROUND:
            continue
        lines[line] = dict(zip(names, fair_probabilities(odds, devig_method)))
    return lines


def _describe_mismatch(market_key: str, sharp: set, target: set) -> str:
    if market_key == "h2h" and ("Draw" in sharp) != ("Draw" in target):
        return "h2h : 1N2 d'un côté, 2 issues de l'autre"
    return f"{market_key} : issues différentes"


def compare_event(
    event: dict,
    devig_method: str = "multiplicative",
    now: Optional[datetime] = None,
    stats: Optional[DetectionStats] = None,
) -> List[ComparedOutcome]:
    """Toutes les issues Betclic d'un match avec leur probabilité réelle Pinnacle."""
    now = now or datetime.now(timezone.utc)
    stats = stats if stats is not None else DetectionStats()
    commence = parse_time(event["commence_time"])
    if commence <= now:
        stats.skipped["match déjà commencé"] += 1
        return []

    stats.events += 1
    books = {b["key"]: b for b in event.get("bookmakers", [])}
    sharp, target = books.get(rules.SHARP_BOOK), books.get(rules.TARGET_BOOK)
    if not sharp:
        stats.skipped["match sans Pinnacle"] += 1
    if not target:
        stats.skipped["match sans Betclic"] += 1
    if not sharp or not target:
        return []
    stats.events_with_both += 1

    home, away = event["home_team"], event["away_team"]
    compared: List[ComparedOutcome] = []

    for market_key in rules.SUPPORTED_MARKETS:
        sharp_market, target_market = _find_market(sharp, market_key), _find_market(target, market_key)
        if not sharp_market or not target_market:
            if sharp_market or target_market:
                absent = "Betclic" if sharp_market else "Pinnacle"
                stats.skipped[f"{market_key} : marché absent chez {absent}"] += 1
            continue
        sharp_lines = group_outcomes(market_key, sharp_market["outcomes"], home)
        target_lines = group_outcomes(market_key, target_market["outcomes"], home)

        for line, target_outcomes in target_lines.items():
            sharp_outcomes = sharp_lines.get(line)
            if not sharp_outcomes:
                stats.skipped[f"{market_key} : ligne Betclic absente chez Pinnacle"] += 1
                continue
            names = set(sharp_outcomes)
            # Même ensemble d'issues des deux côtés, sinon les probabilités ne sont pas comparables.
            if names != set(target_outcomes) or not _is_complete(market_key, names, home, away):
                stats.skipped[_describe_mismatch(market_key, names, set(target_outcomes))] += 1
                continue

            ordered = sorted(names)
            sharp_odds = [float(sharp_outcomes[n]["price"]) for n in ordered]
            target_odds = [float(target_outcomes[n]["price"]) for n in ordered]
            if any(o <= 1.0 for o in sharp_odds + target_odds):
                stats.skipped[f"{market_key} : cote invalide"] += 1
                continue
            margin = sum(1.0 / o for o in sharp_odds)
            if margin > rules.MAX_PINNACLE_OVERROUND:
                log.warning("Marge Pinnacle aberrante (%.3f) sur %s vs %s / %s", margin, home, away, market_key)
                stats.skipped[f"{market_key} : marge Pinnacle > 12 %"] += 1
                continue
            stats.compared[market_key] += 1
            fair = dict(zip(ordered, fair_probabilities(sharp_odds, devig_method)))
            betclic_margin = sum(1.0 / o for o in target_odds)
            evs = {n: expected_value(fair[n], float(target_outcomes[n]["price"])) for n in ordered}
            best = max(evs, key=evs.get)

            for name in ordered:
                outcome = target_outcomes[name]
                point = outcome.get("point")
                point = float(point) if point is not None else None
                compared.append(ComparedOutcome(
                    event_id=event["id"],
                    sport_key=event["sport_key"],
                    home_team=home,
                    away_team=away,
                    commence_time=commence,
                    market=market_key,
                    outcome_name=name,
                    point=point,
                    selection=selection_label(market_key, name, point),
                    betclic_odd=float(outcome["price"]),
                    pinnacle_odd=float(sharp_outcomes[name]["price"]),
                    fair_prob=fair[name],
                    ev=evs[name],
                    pinnacle_overround=margin,
                    betclic_overround=betclic_margin,
                    best_in_grid=name == best,
                ))
    return compared
