"""Analyste quantitatif & contextuel : Score d'Opportunité /100 et 3 profils (CLAUDE.md §3).

Trois piliers, pour chaque issue Betclic comparée à Pinnacle :
1. Marché (35 pts) : probabilité réelle Pinnacle, située dans la plage de son profil.
2. Cote (35 pts) : écart entre la cote Betclic et la cote juste (EV de −3.5 % → 0, ≥ +5 % → 35).
3. Stats (30 pts) : convergence des statistiques ESPN avec le pari (forme, domicile, classement, moyennes).
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Sequence, Tuple

from . import rules
from .detector import ComparedOutcome, DetectionStats
from .models import Opportunity
from .stats_client import TeamStats
from .value import profile_stake

log = logging.getLogger(__name__)

REJECT_ODD = "cote hors profils (1.40–3.80)"
REJECT_EV = f"EV < {rules.MIN_EV * 100:g} %"
REJECT_SAFE_PROB = "Safe : proba Pinnacle < 56 %"
REJECT_SAFE_NO_STATS = "Safe : stats indisponibles"
REJECT_STATS = "stats non convergentes"
REJECT_LOW_EV_STATS = f"EV < {rules.STANDARD_MARGIN_EV * 100:g} % sans stats ≥ {rules.MIN_STATS_POINTS_LOW_EV}/30"

# Calibrage par sport : (échelle de différence/match, avantage du terrain, seuil « défense friable »)
_SCALES = {"soccer": (4.0, 0.25, 1.6), "basketball": (30.0, 2.0, 118.0)}
_TOTAL_SCALE = {"soccer": 1.2, "basketball": 12.0}
_SPREAD_SCALE = {"soccer": 1.0, "basketball": 10.0}


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def classify_profile(odd: float) -> Optional[str]:
    for profile in rules.PROFILES:
        lo, hi = rules.ODD_RANGES[profile]
        if lo <= odd < hi or (profile == rules.PROFILES[-1] and odd == hi):
            return profile
    return None


# --- Pilier 3 : convergence statistique --------------------------------------------------
@dataclass
class Convergence:
    score: Optional[float]                       # 0 → 1, None si stats indisponibles
    facts: List[str] = field(default_factory=list)          # arguments, du plus parlant au moins parlant
    risks: List[Tuple[float, str]] = field(default_factory=list)  # (gravité, texte)
    headline: str = ""                                       # 1 phrase pour Telegram


def team_rating(team: TeamStats, home: bool) -> Optional[float]:
    """Force 0 → 1 d'une équipe pour ce match : forme, bilan sur ce terrain, classement, différence."""
    diff_scale = _SCALES[team.sport][0]
    diff = team.diff_per_game
    parts = [
        (0.35, team.form_ratio),
        (0.25, team.venue_ratio(home)),
        (0.20, None if team.rank_ratio is None else team.rank_ratio * team.league_strength),
        (0.20, None if diff is None else _clamp(0.5 + diff / diff_scale)),
    ]
    known = [(w, v) for w, v in parts if v is not None]
    if not known:
        return None
    return sum(w * v for w, v in known) / sum(w for w, _ in known)


def _ordinal(n: Optional[int]) -> str:
    if not n:
        return "?"
    return "1er" if n == 1 else f"{n}e"


def _form_fact(t: TeamStats) -> Optional[str]:
    if not t.games:
        return None
    last = t.last(5)
    if t.is_soccer:
        pts = sum({"V": 3, "N": 1, "D": 0}[g.result] for g in last)
        return f"{t.name} : forme {t.form} ({pts}/{3 * len(last)} pts sur les {len(last)} derniers matchs)"
    wins = sum(g.result == "V" for g in last)
    return f"{t.name} : {wins} victoire(s) sur les {len(last)} derniers matchs ({t.form})"


def _venue_fact(t: TeamStats, home: bool) -> Optional[str]:
    games = t.venue_games(home)
    if len(games) < 2:
        return None
    w, d, l = t.venue_record(home)
    where = "à domicile" if home else "à l'extérieur"
    record = f"{w}V-{d}N-{l}D" if t.is_soccer else f"{w}V-{l}D"
    return f"{t.name} {where} cette saison : {record}"


def _rank_fact(h: TeamStats, a: TeamStats) -> Optional[str]:
    if not h.rank or not a.rank:
        return None
    if h.competition != a.competition:
        return (f"Classement national : {h.name} {_ordinal(h.rank)} de {h.competition_name} · "
                f"{a.name} {_ordinal(a.rank)} de {a.competition_name}")
    return f"Classement : {h.name} {_ordinal(h.rank)} · {a.name} {_ordinal(a.rank)} (sur {h.table_size})"


def _avg_fact(t: TeamStats) -> Optional[str]:
    if t.avg_scored is None or t.avg_conceded is None:
        return None
    return f"{t.name} : {t.avg_scored:.1f} {t.unit} marqués / {t.avg_conceded:.1f} encaissés par match"


def _streak_fact(t: TeamStats) -> Optional[str]:
    result, count = t.streak
    if count < 3:
        return None
    word = {"V": "victoires", "D": "défaites", "N": "nuls"}[result]
    return f"{t.name} reste sur {count} {word} de suite"


def _team_risks(t: TeamStats, opp: TeamStats, home: bool, commence: datetime) -> List[Tuple[float, str]]:
    risks: List[Tuple[float, str]] = []
    last = t.last_game_before(commence)
    if not t.is_soccer and last and commence - last.date < timedelta(hours=30):
        risks.append((3.0, f"Back-to-back : {t.name} a joué la veille (fatigue, rotation possible)"))
    if len(t.injuries) >= 2:
        names = ", ".join(t.injuries[:3])
        risks.append((2.5 if len(t.injuries) >= 3 else 2.0, f"{len(t.injuries)} joueurs incertains/absents chez {t.name} : {names}"))
    threshold = _SCALES[t.sport][2]
    if t.avg_conceded is not None and t.avg_conceded >= threshold:
        risks.append((2.0, f"Défense friable : {t.name} encaisse {t.avg_conceded:.1f} {t.unit} par match"))
    if t.form_ratio is not None and t.form_ratio <= 0.34:
        risks.append((2.0, f"Forme en berne : {t.name} {t.form} sur ses 5 derniers matchs"))
    if opp.form_ratio is not None and opp.form_ratio >= 0.8:
        risks.append((1.8, f"Adversaire en forme : {opp.name} {opp.form}"))
    venue = t.venue_ratio(home)
    if venue is not None and venue <= 0.3:
        where = "à domicile" if home else "à l'extérieur"
        risks.append((1.8, f"{t.name} peine {where} cette saison ({venue * 100:.0f} % des points pris)"))
    return risks


def _blend(t: TeamStats) -> Tuple[Optional[float], Optional[float]]:
    """Moyennes marquées/encaissées pondérées saison (60 %) / 5 derniers matchs (40 %)."""
    s, c = t.avg_scored, t.avg_conceded
    ls, lc = t.last_averages(5)
    if s is None or c is None:
        return ls, lc
    if ls is None or lc is None:
        return s, c
    return 0.6 * s + 0.4 * ls, 0.6 * c + 0.4 * lc


def _fr(x: float) -> str:
    return f"{x:.1f}".replace(".", ",")


def _team_pick(outcome: ComparedOutcome, home: TeamStats, away: TeamStats, name: str):
    pick_home = name == outcome.home_team
    team, opp = (home, away) if pick_home else (away, home)
    label, opp_label = (outcome.home_team, outcome.away_team) if pick_home else (outcome.away_team, outcome.home_team)
    return pick_home, team, opp, label, opp_label


def _team_headline(team: TeamStats, opp: TeamStats, label: str, opp_label: str, home: bool) -> str:
    w, d, l = team.venue_record(home)
    where = "à domicile" if home else "à l'extérieur"
    if len(team.venue_games(home)) >= 3:
        rec = f"{w}V-{d}N-{l}D" if team.is_soccer else f"{w}V-{l}D"
        return f"{label} : {rec} {where}, forme {team.form} contre {opp.form} pour {opp_label}"
    return f"{label} en forme {team.form}, {opp_label} {opp.form} sur les 5 derniers matchs"


def stats_convergence(outcome: ComparedOutcome, home: Optional[TeamStats],
                      away: Optional[TeamStats]) -> Convergence:
    if home is None or away is None:
        return Convergence(None, [], [(1.5, "Statistiques indisponibles : analyse fondée sur les cotes seules")],
                           headline=f"Pinnacle lui donne {outcome.fair_prob * 100:.0f} % de chances")
    sport = home.sport
    conv = Convergence(None)
    hn, an = outcome.home_team, outcome.away_team
    market, name = outcome.market, outcome.outcome_name

    if market in ("h2h", "dnb", "double_chance"):
        rh, ra = team_rating(home, True), team_rating(away, False)
        if rh is None or ra is None:
            return Convergence(None, [], [(1.5, "Statistiques trop maigres en début de saison")],
                               headline=f"Pinnacle lui donne {outcome.fair_prob * 100:.0f} % de chances")
        if market == "h2h" and name == "Draw":
            closeness = _clamp(1 - 2.5 * abs(rh - ra))
            draws = [r for r in (home.draw_ratio, away.draw_ratio) if r is not None]
            draw_rate = sum(draws) / len(draws) if draws else 0.25
            conv.score = 0.6 * closeness + 0.4 * _clamp(draw_rate / 0.35)
            conv.facts = [f for f in (_rank_fact(home, away), _form_fact(home), _form_fact(away)) if f]
            if draws:
                conv.facts.append(f"Taux de nuls récents : {home.name} {home.draw_ratio * 100:.0f} % · "
                                  f"{away.name} {away.draw_ratio * 100:.0f} %")
                conv.headline = (f"Deux équipes proches, {home.draw_ratio * 100:.0f} % et "
                                 f"{away.draw_ratio * 100:.0f} % de nuls sur leurs 10 derniers matchs")
            conv.risks = [(1.6, "Le nul est l'issue la plus difficile à anticiper : un but change tout")]
            return conv
        if market == "double_chance":
            # 1X / X2 : l'équipe couverte ne doit pas perdre ; 12 : il faut un vainqueur.
            if name == "12":
                conv.score = _clamp(0.4 + 1.2 * abs(rh - ra))
                conv.facts = [f for f in (_rank_fact(home, away), _form_fact(home), _form_fact(away)) if f]
                conv.headline = f"Écart de niveau marqué : peu de chances de nul"
                return conv
            name = hn if name == "1X" else an
            pick_home, team, opp, label, opp_label = _team_pick(outcome, home, away, name)
            diff = (rh - ra) if pick_home else (ra - rh)
            conv.score = _clamp(0.6 + 0.9 * diff)
        else:
            pick_home, team, opp, label, opp_label = _team_pick(outcome, home, away, name)
            diff = (rh - ra) if pick_home else (ra - rh)
            conv.score = _clamp(0.5 + 0.9 * diff)
        conv.facts = [f for f in (_form_fact(team), _venue_fact(team, pick_home), _rank_fact(home, away),
                                  _streak_fact(team), _avg_fact(team), _form_fact(opp)) if f]
        conv.headline = _team_headline(team, opp, label, opp_label, pick_home)
        conv.risks = _team_risks(team, opp, pick_home, outcome.commence_time)
        return conv

    if market == "btts":
        rates = [home.scored_rate(), away.scored_rate(), home.conceded_rate(), away.conceded_rate()]
        if None in rates:
            return Convergence(None, [], [(1.5, "Historique de buts indisponible")])
        hs_r, as_r, hc_r, ac_r = rates
        both = math.sqrt(hs_r * ac_r) * math.sqrt(as_r * hc_r)  # chaque attaque contre la défense adverse
        yes = name == "Yes"
        conv.score = _clamp(0.5 + ((both - 0.5) if yes else (0.5 - both)) * 1.5)
        n = len(home.last(10)), len(away.last(10))
        conv.facts = [f"{hn} a marqué dans {round(hs_r * n[0])}/{n[0]} matchs, {an} dans {round(as_r * n[1])}/{n[1]}",
                      f"{hn} a encaissé dans {round(hc_r * n[0])}/{n[0]} matchs, {an} dans {round(ac_r * n[1])}/{n[1]}"]
        if yes:
            conv.headline = (f"{hn} a marqué dans {round(hs_r * n[0])} de ses {n[0]} derniers matchs, "
                             f"{an} dans {round(as_r * n[1])}/{n[1]}")
        else:
            tight = home if hc_r < ac_r else away
            conv.headline = (f"{hn if tight is home else an} n'a encaissé que dans "
                             f"{round(min(hc_r, ac_r) * len(tight.last(10)))}/{len(tight.last(10))} matchs")
            conv.risks.append((1.8, "Un seul but encaissé par chaque équipe suffit à faire perdre le « Non »"))
        return conv

    if market == "team_totals" and outcome.point is not None:
        team_name, side = name.rsplit(" ", 1)
        pick_home, team, opp, label, opp_label = _team_pick(outcome, home, away, team_name)
        ts, _ = _blend(team)
        _, oc = _blend(opp)
        if ts is None or oc is None:
            return Convergence(None, [], [(1.5, "Moyennes de buts indisponibles")])
        expected = (ts + oc) / 2
        gap = expected - outcome.point
        conv.score = _clamp(0.5 + (gap if side == "Over" else -gap) / 1.6)
        conv.facts = [f"Buts attendus pour {label} : {expected:.1f} (ligne {outcome.point:g})",
                      *[f for f in (_avg_fact(team), _avg_fact(opp)) if f]]
        conv.headline = f"{label} marque {_fr(ts)} buts/match, {opp_label} en encaisse {_fr(oc)}"
        conv.risks = _team_risks(team, opp, pick_home, outcome.commence_time)[:1]
        return conv

    if market == "totals" and outcome.point is not None:
        hs, hc = _blend(home)
        as_, ac = _blend(away)
        if None in (hs, hc, as_, ac):
            return Convergence(None, [], [(1.5, "Moyennes de buts/points indisponibles")])
        expected = (hs + ac) / 2 + (as_ + hc) / 2
        gap = expected - outcome.point
        over = name == "Over"
        conv.score = _clamp(0.5 + (gap if over else -gap) / (2 * _TOTAL_SCALE[sport]))
        unit = home.unit
        conv.facts = [f"Total attendu d'après les moyennes : {expected:.1f} {unit} (ligne {outcome.point:g})"]
        conv.facts += [f for f in (_avg_fact(home), _avg_fact(away)) if f]
        conv.headline = (f"{_fr(expected)} {unit} attendus : {hn} {_fr(hs)} marqués/{_fr(hc)} encaissés, "
                         f"{an} {_fr(as_)}/{_fr(ac)} par match")
        if over and min(hs, as_) < expected / 3:
            weak = home if hs < as_ else away
            conv.risks.append((1.8, f"Attaque limitée : {weak.name} ne marque que {min(hs, as_):.1f} {unit} par match"))
        if not over and max(hc, ac) >= _SCALES[sport][2]:
            leaky = home if hc > ac else away
            conv.risks.append((2.0, f"Défense friable : {leaky.name} encaisse {max(hc, ac):.1f} {unit} par match"))
        return conv

    if market == "spreads" and outcome.point is not None:
        pick_home, team, opp, label, opp_label = _team_pick(outcome, home, away, name)
        if team.diff_per_game is None or opp.diff_per_game is None:
            return Convergence(None, [], [(1.5, "Différences de buts/points indisponibles")])
        adv = _SCALES[sport][1] if pick_home else -_SCALES[sport][1]
        margin = (team.diff_per_game - opp.diff_per_game) / 2 + adv
        conv.score = _clamp(0.5 + (margin + outcome.point) / (2 * _SPREAD_SCALE[sport]))
        conv.facts = [f"Écart attendu : {team.name} {margin:+.1f} {team.unit} (handicap {outcome.point:+g})",
                      *[f for f in (_avg_fact(team), _avg_fact(opp), _venue_fact(team, pick_home)) if f]]
        conv.headline = (f"Différence par match : {label} {team.diff_per_game:+.1f}, "
                         f"{opp_label} {opp.diff_per_game:+.1f}").replace(".", ",")
        conv.risks = _team_risks(team, opp, pick_home, outcome.commence_time)
        return conv
    return Convergence(None)


# --- Score et sélection --------------------------------------------------------------------
def _market_points(profile: str, prob: float) -> float:
    lo, hi = rules.PROB_SCORE_RANGE[profile]
    return rules.SCORE_WEIGHTS["marche"] * _clamp((prob - lo) / (hi - lo))


def _price_points(ev: float) -> float:
    return rules.SCORE_WEIGHTS["cote"] * _clamp((ev - rules.MIN_EV) / (rules.EV_SCORE_CEILING - rules.MIN_EV))


def _stats_points(convergence: Optional[float]) -> float:
    value = rules.NEUTRAL_STATS_SCORE if convergence is None else convergence
    return rules.SCORE_WEIGHTS["stats"] * value


def rejection_reason(profile: Optional[str], outcome: ComparedOutcome,
                     convergence: Optional[float]) -> Optional[str]:
    if profile is None:
        return REJECT_ODD
    if outcome.ev < rules.MIN_EV - 1e-9:
        return REJECT_EV
    if profile == rules.PROFILE_SAFE:
        if outcome.fair_prob < rules.SAFE_MIN_FAIR_PROB - 1e-9:
            return REJECT_SAFE_PROB
        if convergence is None:
            return REJECT_SAFE_NO_STATS
    if convergence is not None and convergence < rules.MIN_STATS_SCORE[profile] - 1e-9:
        return REJECT_STATS
    # Marge Betclic standard : on ne garde le pari que si forme, classement et stats le soutiennent vraiment.
    if outcome.ev < rules.STANDARD_MARGIN_EV - 1e-9 and \
            _stats_points(convergence) < rules.MIN_STATS_POINTS_LOW_EV - 1e-9:
        return REJECT_LOW_EV_STATS
    return None


def _arguments(outcome: ComparedOutcome, profile: str, conv: Convergence) -> List[str]:
    p, fair, c = outcome.fair_prob, 1 / outcome.fair_prob, outcome.betclic_odd
    args = [f"Pinnacle, le marché de référence, estime la probabilité réelle à **{p * 100:.1f} %** "
            f"(cote juste {fair:.2f}) : Betclic propose **{c:.2f}**."]
    margin = (outcome.betclic_overround - 1) * 100
    if outcome.estimated:
        args[0] = (f"Probabilité réelle **{p * 100:.1f} %** (cote juste {fair:.2f}), calculée sur les cotes Pinnacle "
                   f"(modèle de Poisson pour les marchés de buts).")
        args.append(f"Cote Betclic non publiée via l'API : **exiger au moins {outcome.min_odd:.2f}** sur Betclic "
                    f"(estimation ≈ {c:.2f} avec sa marge 1N2 de {margin:.1f} % sur ce match).")
    elif outcome.ev >= 0:
        args.append(f"Cote Betclic **{outcome.ev * 100:+.1f} %** au-dessus de la cote juste, malgré une marge "
                    f"de {margin:.1f} % sur ce marché : une vraie value.")
    elif outcome.best_in_grid:
        small = "seulement " if outcome.ev >= rules.STANDARD_MARGIN_EV else ""
        args.append(f"Écart de {small}{outcome.ev * 100:.1f} % avec la cote juste alors que Betclic prend "
                    f"{margin:.1f} % de marge sur ce marché : c'est l'issue la mieux payée de sa grille.")
    else:
        args.append(f"Écart limité à {outcome.ev * 100:.1f} % avec la cote juste (marge Betclic du marché : {margin:.1f} %).")
    if conv.facts:
        args.extend(conv.facts[:2])
    else:
        args.append("Pas de statistiques ESPN pour cette compétition : le pick repose sur le marché uniquement.")
    return args[:4]


def _vigilance(outcome: ComparedOutcome, profile: str, conv: Convergence) -> List[str]:
    risks = list(conv.risks)
    if profile == rules.PROFILE_AUDACIEUX:
        risks.append((1.4, f"Pari risqué : {outcome.fair_prob * 100:.0f} % de chances selon Pinnacle, "
                           "attendez-vous à perdre plus souvent qu'à gagner"))
    if outcome.ev < 0:
        level = "légèrement négative" if outcome.ev >= rules.STANDARD_MARGIN_EV else "négative"
        risks.append((1.0, f"Marge bookmaker : cote {abs(outcome.ev) * 100:.1f} % sous la cote juste, "
                           f"espérance {level} selon Pinnacle (≈ {abs(outcome.ev) * 100:.0f} cts perdus "
                           "par euro misé en moyenne)"))
    risks.sort(key=lambda r: -r[0])
    return [text for _, text in risks[:2]] or ["Aucun signal d'alerte particulier dans les chiffres"]


def analyze(outcome: ComparedOutcome, sport_name: str, league_name: str, bankroll: float,
            home: Optional[TeamStats], away: Optional[TeamStats],
            stats: Optional[DetectionStats] = None) -> Optional[Opportunity]:
    """Note une issue ; None si elle ne rentre dans aucun profil."""
    stats = stats if stats is not None else DetectionStats()
    profile = classify_profile(outcome.betclic_odd)
    conv = stats_convergence(outcome, home, away) if profile else Convergence(None)
    reason = rejection_reason(profile, outcome, conv.score)
    if reason:
        stats.rejections[reason] += 1
        if reason == REJECT_EV:
            stats.near_misses.append((outcome.ev, profile, f"{outcome.home_team} vs {outcome.away_team} · "
                                      f"{outcome.selection} @ {outcome.betclic_odd:.2f}"))
        return None
    stats.candidates[profile] += 1

    market_pts = _market_points(profile, outcome.fair_prob)
    price_pts = _price_points(outcome.ev)
    stats_pts = _stats_points(conv.score)
    stake, pct, theoretical = profile_stake(profile, bankroll)
    return Opportunity(
        event_id=outcome.event_id, sport_key=outcome.sport_key, sport=sport_name, ligue=league_name,
        home_team=outcome.home_team, away_team=outcome.away_team, commence_time=outcome.commence_time,
        market=outcome.market, outcome_name=outcome.outcome_name, point=outcome.point,
        selection=outcome.selection, betclic_odd=outcome.betclic_odd, pinnacle_odd=outcome.pinnacle_odd,
        fair_prob=outcome.fair_prob, ev=outcome.ev, pinnacle_overround=outcome.pinnacle_overround,
        betclic_overround=outcome.betclic_overround, profile=profile,
        score=int(round(market_pts + price_pts + stats_pts)),
        score_market=round(market_pts, 1), score_price=round(price_pts, 1), score_stats=round(stats_pts, 1),
        stats_convergence=None if conv.score is None else round(conv.score, 3),
        estimated=outcome.estimated, min_odd=outcome.min_odd,
        headline=conv.headline or (conv.facts[0] if conv.facts else
                                   f"Pinnacle lui donne {outcome.fair_prob * 100:.0f} % de chances"),
        stake=stake, stake_pct=pct, stake_theoretical=theoretical,
        arguments=tuple(_arguments(outcome, profile, conv)),
        vigilance=tuple(_vigilance(outcome, profile, conv)),
        key_stats=tuple(conv.facts[:3]),
        home_stats=home, away_stats=away,
    )


def _convergence_key(opp: Opportunity) -> Tuple[float, int]:
    conv = rules.NEUTRAL_STATS_SCORE if opp.stats_convergence is None else opp.stats_convergence
    return conv, opp.score


def select_top(opportunities: Sequence[Opportunity], limit: int = rules.MAX_PICKS_PER_SCAN) -> List[Opportunity]:
    """Top du scan (CLAUDE.md §3) :
    - un seul pari par match : le marché à la meilleure convergence statistique (puis au meilleur score) ;
    - le meilleur de chaque profil d'abord, puis les matchs par score décroissant ;
    - au plus `MAX_PICKS_PER_MARKET` paris du même type de marché, pour varier les paris ;
      si cela laisse des places vides faute d'autre marché (tennis…), on complète sans ce plafond.
    """
    by_event: Dict[str, List[Opportunity]] = {}
    for opp in opportunities:
        by_event.setdefault(opp.event_id, []).append(opp)
    for opps in by_event.values():
        opps.sort(key=_convergence_key, reverse=True)

    picks: List[Opportunity] = []
    per_market: Dict[str, int] = {}

    def accept(opp: Opportunity, capped: bool = True) -> bool:
        if len(picks) >= limit or any(p.event_id == opp.event_id for p in picks) \
                or (capped and per_market.get(opp.market, 0) >= rules.MAX_PICKS_PER_MARKET):
            return False
        picks.append(opp)
        per_market[opp.market] = per_market.get(opp.market, 0) + 1
        return True

    for profile in rules.PROFILES:
        # Un représentant par profil : pour chaque match, son marché le plus convergent dans ce profil,
        # puis le meilleur score ; si possible sans dépasser le plafond par marché.
        candidates = sorted((next(o for o in opps if o.profile == profile) for opps in by_event.values()
                             if any(o.profile == profile for o in opps)),
                            key=lambda o: (o.score, o.ev), reverse=True)
        if not any(accept(o) for o in candidates):
            any(accept(o, capped=False) for o in candidates)
    events = sorted(by_event.values(), key=lambda opps: max(o.score for o in opps), reverse=True)
    for capped in (True, False):
        for opps in events:
            for opp in opps:  # marché le plus convergent d'abord
                if accept(opp, capped):
                    break
    return sorted(picks, key=lambda o: (o.score, o.ev), reverse=True)
