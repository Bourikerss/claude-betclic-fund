"""Marchés internes au match que The Odds API ne fournit pas pour Betclic (football uniquement).

Double chance et Remboursé si nul se déduisent exactement du 1N2 Pinnacle sans marge.
Over/Under, buts d'une équipe, les deux équipes marquent et handicap ±1.5 viennent du modèle de
Poisson (`poisson.py`) calibré sur Pinnacle (1N2 + totals) et, à défaut de totals, sur les moyennes ESPN.

Betclic ne publiant pas ces cotes via l'API, on estime sa cote en appliquant au marché sa marge
1N2 constatée sur le même match, et on affiche la **cote minimale à exiger** :
`cote juste × (1 + MIN_EV)`. En dessous, le pari sort des règles (EV < −10 %).
"""
from __future__ import annotations

import math
from dataclasses import replace
from typing import Dict, List, Optional

from . import rules
from .detector import ComparedOutcome, pinnacle_fair_lines
from .poisson import ScoreModel, fit
from .stats_client import TeamStats


def _ceil2(x: float) -> float:
    return math.ceil(x * 100 - 1e-9) / 100


def prior_total(home: Optional[TeamStats], away: Optional[TeamStats]) -> Optional[float]:
    """Total de buts attendu d'après ESPN : (attaque dom. + défense ext.)/2 + (attaque ext. + défense dom.)/2."""
    if not home or not away:
        return None
    values = (home.avg_scored, away.avg_conceded, away.avg_scored, home.avg_conceded)
    if any(v is None for v in values):
        return None
    hs, ac, as_, hc = values
    return (hs + ac) / 2 + (as_ + hc) / 2


def build_model(event: dict, h2h_fair: Dict[str, float], home: Optional[TeamStats], away: Optional[TeamStats],
                devig_method: str = "multiplicative") -> ScoreModel:
    target = (h2h_fair[event["home_team"]], h2h_fair["Draw"], h2h_fair[event["away_team"]])
    totals = pinnacle_fair_lines(event, "totals", devig_method)
    over = None
    if totals:
        line = min(totals, key=lambda l: abs(l - 2.5))  # ligne principale, la plus proche de 2.5
        over = (line, totals[line]["Over"])
    prior = prior_total(home, away) or rules.POISSON_DEFAULT_TOTAL
    return fit(target, over=over, prior_total=prior)


def derive_outcomes(event: dict, h2h: List[ComparedOutcome], home: Optional[TeamStats],
                    away: Optional[TeamStats], devig_method: str = "multiplicative") -> List[ComparedOutcome]:
    """Toutes les issues dérivées d'un match de football à partir de ses issues 1N2 comparées."""
    by_name = {o.outcome_name: o for o in h2h if o.market == "h2h"}
    home_team, away_team = event["home_team"], event["away_team"]
    if {home_team, away_team, "Draw"} - set(by_name):
        return []  # il faut le 1N2 complet (football)
    fair = {name: o.fair_prob for name, o in by_name.items()}
    base = by_name[home_team]
    betclic_margin = base.betclic_overround
    model = build_model(event, fair, home, away, devig_method)
    p1, px, p2 = fair[home_team], fair["Draw"], fair[away_team]
    pin_totals = pinnacle_fair_lines(event, "totals", devig_method)

    def make(market: str, name: str, selection: str, prob: float, point: Optional[float] = None) -> ComparedOutcome:
        fair_odd = 1 / prob
        est = fair_odd / betclic_margin  # pas d'arrondi : il gonflerait l'EV estimée (bug du 03/11/2026)
        return replace(
            base, market=market, outcome_name=name, point=point, selection=selection,
            betclic_odd=est, pinnacle_odd=round(fair_odd, 2), fair_prob=prob, ev=prob * est - 1,
            best_in_grid=False, estimated=True, min_odd=_ceil2(fair_odd * (1 + rules.MIN_EV)))

    out: List[ComparedOutcome] = [
        make("double_chance", "1X", f"{home_team} ou nul", p1 + px),
        make("double_chance", "X2", f"Nul ou {away_team}", px + p2),
        make("dnb", home_team, f"{home_team} (remboursé si nul)", p1 / (p1 + p2)),
        make("dnb", away_team, f"{away_team} (remboursé si nul)", p2 / (p1 + p2)),
    ]
    btts = model.btts()
    out += [make("btts", "Yes", "Les 2 équipes marquent : Oui", btts),
            make("btts", "No", "Les 2 équipes marquent : Non", 1 - btts)]
    for line in rules.DERIVED_TOTAL_LINES:
        # Ligne cotée par Pinnacle : sa probabilité sans marge prime sur le modèle.
        p_over = pin_totals[line]["Over"] if line in pin_totals else model.over(line)
        out += [make("totals", "Over", f"Plus de {line:g} buts", p_over, line),
                make("totals", "Under", f"Moins de {line:g} buts", 1 - p_over, line)]
    for team, is_home in ((home_team, True), (away_team, False)):
        for line in rules.DERIVED_TEAM_LINES:
            p = model.team_over(is_home, line)
            unit = "but" if line < 1 else "buts"
            out += [make("team_totals", f"{team} Over", f"{team} : plus de {line:g} {unit}", p, line),
                    make("team_totals", f"{team} Under", f"{team} : moins de {line:g} {unit}", 1 - p, line)]
        p_cover = model.margin_at_least(is_home, int(rules.DERIVED_SPREAD + 0.5))
        out += [make("spreads", team, f"{team} -{rules.DERIVED_SPREAD:g}", p_cover, -rules.DERIVED_SPREAD)]
        opponent = away_team if is_home else home_team
        out += [make("spreads", opponent, f"{opponent} +{rules.DERIVED_SPREAD:g}", 1 - p_cover, rules.DERIVED_SPREAD)]
    return [o for o in out if 0.0 < o.fair_prob < 1.0]
