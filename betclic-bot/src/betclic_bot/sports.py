"""Catalogue des sports : éligibilité, noms français et poids de priorité."""
from __future__ import annotations

from typing import Dict, List

from .stats_client import ESPN_LEAGUES

# Famille The Odds API → nom français (= nom de la note hub Obsidian)
SPORT_FR = {
    "Soccer": "Football",
    "Basketball": "Basketball",
    "Tennis": "Tennis",
    "Ice Hockey": "Hockey sur glace",
    "American Football": "Football américain",
    "Baseball": "Baseball",
    "Rugby Union": "Rugby à XV",
    "Rugby League": "Rugby à XIII",
    "Handball": "Handball",
    "Mixed Martial Arts": "MMA",
    "Boxing": "Boxe",
}

EMOJI = {
    "Football": "⚽", "Basketball": "🏀", "Tennis": "🎾", "Hockey sur glace": "🏒",
    "Football américain": "🏈", "Baseball": "⚾", "Rugby à XV": "🏉", "Rugby à XIII": "🏉",
    "Handball": "🤾", "MMA": "🥊", "Boxe": "🥊",
}

# Noms de ligues plus lisibles que les `title` de l'API
LEAGUE_FR = {
    "EPL": "Premier League",
    "Ligue 1 - France": "Ligue 1",
    "Ligue 2 - France": "Ligue 2",
    "La Liga - Spain": "La Liga",
    "Serie A - Italy": "Serie A",
    "Bundesliga - Germany": "Bundesliga",
    "UEFA Champions League": "Ligue des Champions",
    "UEFA Europa League": "Ligue Europa",
    "UEFA Europa Conference League": "Ligue Conférence",
}

# Poids de priorité : plus il est élevé, plus le sport est scanné souvent.
# Depuis le 03/11/2026, seules les compétitions couvertes par ESPN (stats + scores pour le
# règlement automatique) sont scannées. Le tennis n'y est pas : ni stats ni scores ESPN exploitables.
PRIORITY_WEIGHTS = {
    "soccer_epl": 3.0,
    "soccer_france_ligue_one": 3.0,
    "soccer_uefa_champs_league": 3.0,
    "soccer_spain_la_liga": 2.5,
    "soccer_italy_serie_a": 2.5,
    "soccer_germany_bundesliga": 2.5,
    "soccer_uefa_europa_league": 2.5,
    "basketball_nba": 2.0,  # couvert par ESPN mais Betclic absent de The Odds API (02/11/2026)
}
DEFAULT_WEIGHT = 0.5


def sport_name(group: str) -> str:
    return SPORT_FR.get(group, group)


def league_name(title: str) -> str:
    return LEAGUE_FR.get(title, title)


def sport_weight(sport: dict) -> float:
    key = sport["key"]
    if key in PRIORITY_WEIGHTS:
        return PRIORITY_WEIGHTS[key]
    return DEFAULT_WEIGHT


def eligible_sports(sports: List[dict]) -> Dict[str, dict]:
    """Sports actifs, hors outrights, couverts par ESPN (stats et scores finaux).

    Aucun crédit n'est dépensé sur une compétition sans statistiques (Championship, Brésil, tennis…).
    """
    return {
        s["key"]: s
        for s in sports
        if s.get("active") and not s.get("has_outrights") and s.get("group") in SPORT_FR
        and s["key"] in ESPN_LEAGUES
    }
