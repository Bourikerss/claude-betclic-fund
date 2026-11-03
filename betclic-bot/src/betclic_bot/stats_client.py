"""Statistiques d'équipes gratuites via les endpoints JSON publics d'ESPN (aucune clé).

- Classement : `apis/v2/sports/{sport}/{league}/standings` (1 appel par compétition).
- Résultats d'une équipe : `apis/site/v2/sports/{sport}/{league}/teams/{id}/schedule`.
- Blessures NBA : `apis/site/v2/sports/basketball/nba/injuries`.

Toutes les réponses sont mises en cache 24 h dans `data/espn_cache/` : un scan ne refait
pas d'appel pour une équipe déjà vue dans la journée. En cas de panne réseau, le cache
expiré est réutilisé ; à défaut, les stats sont absentes et l'analyse reste neutre.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import requests

log = logging.getLogger(__name__)

BASE = "https://site.api.espn.com/apis"
STANDINGS_URL = BASE + "/v2/sports/{sport}/{league}/standings"
SCHEDULE_URL = BASE + "/site/v2/sports/{sport}/{league}/teams/{team_id}/schedule"
INJURIES_URL = BASE + "/site/v2/sports/{sport}/{league}/injuries"

# Clé The Odds API → (sport ESPN, compétition ESPN)
ESPN_LEAGUES: Dict[str, Tuple[str, str]] = {
    "soccer_epl": ("soccer", "eng.1"),
    "soccer_france_ligue_one": ("soccer", "fra.1"),
    "soccer_spain_la_liga": ("soccer", "esp.1"),
    "soccer_italy_serie_a": ("soccer", "ita.1"),
    "soccer_germany_bundesliga": ("soccer", "ger.1"),
    "soccer_uefa_champs_league": ("soccer", "uefa.champions"),
    "soccer_uefa_europa_league": ("soccer", "uefa.europa"),
    "basketball_nba": ("basketball", "nba"),
}
# Championnats nationaux couverts par ESPN → (nom, force relative ≈ coefficient UEFA, 1 = le plus fort).
# En coupe d'Europe, le niveau d'un club se lit dans son championnat national, pondéré par cette force.
DOMESTIC_LEAGUES = {
    "eng.1": ("Premier League", 1.00), "esp.1": ("Liga", 0.97), "ita.1": ("Serie A", 0.95),
    "ger.1": ("Bundesliga", 0.94), "fra.1": ("Ligue 1", 0.88), "por.1": ("Primeira Liga", 0.80),
    "ned.1": ("Eredivisie", 0.78), "bel.1": ("Pro League", 0.72), "tur.1": ("Süper Lig", 0.70),
    "aut.1": ("Bundesliga autrichienne", 0.65), "sco.1": ("Premiership écossaise", 0.62),
    "gre.1": ("Super League grecque", 0.62), "den.1": ("Superliga danoise", 0.60),
    "nor.1": ("Eliteserien", 0.58), "swe.1": ("Allsvenskan", 0.55), "cyp.1": ("Championnat chypriote", 0.52),
    "isr.1": ("Ligat HaAl", 0.52),
}
DOMESTIC_SOCCER = tuple(DOMESTIC_LEAGUES)
EUROPEAN_SOCCER = ("uefa.champions", "uefa.europa")
COMPETITION_NAMES = {"uefa.champions": "Ligue des Champions", "uefa.europa": "Ligue Europa", "nba": "NBA",
                     **{k: v[0] for k, v in DOMESTIC_LEAGUES.items()}}

# --- Rapprochement des noms The Odds API ↔ ESPN -------------------------------------
_STOPWORDS = {"fc", "afc", "cf", "sc", "ac", "as", "ssc", "us", "rc", "cd", "ud", "sd", "club", "de", "del",
              "the", "calcio", "fk", "sk", "sv", "vfb", "vfl", "tsg", "bsc", "and", "ogc", "osc", "stade",
              "olympique", "fsv", "rb", "pfc"}
# Nom normalisé côté The Odds API → nom normalisé côté ESPN (cas que le flou ne tranche pas).
ALIASES = {
    "inter milan": "internazionale",
    "inter": "internazionale",
    "athletic bilbao": "athletic",
    "sporting lisbon": "sporting cp",
    "rennes": "rennais",
    "los angeles clippers": "la clippers",
    "psg": "paris saint germain",
    "koln": "cologne",
    "feyenoord": "feyenoord rotterdam",
    "olympiakos piraeus": "olympiacos",
    "olympiakos": "olympiacos",
    "omonoia": "omonia nicosia",
    "lask": "lask linz",
    "slavia praha": "slavia prague",
    "ferencvaros tc": "ferencvaros",
}
MIN_MATCH_SCORE = 0.75


def normalize_team(name: str) -> str:
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    text = text.replace("&", " and ")
    # Les numéros (« Mainz 05 », « 1. FC ») ne distinguent jamais deux clubs d'une même ligue.
    tokens = [t for t in re.split(r"[^a-z0-9]+", text) if t and t not in _STOPWORDS and not t.isdigit()]
    return " ".join(tokens)


def _token_sim(a: str, b: str) -> float:
    if a == b:
        return 1.0
    if min(len(a), len(b)) >= 4 and (a.startswith(b) or b.startswith(a)):
        return 0.9  # « lyon » / « lyonnais », « brest » / « brestois »
    ratio = SequenceMatcher(None, a, b).ratio()
    return ratio if ratio >= 0.85 else 0.0


def _directional(a: Sequence[str], b: Sequence[str]) -> float:
    return sum(max(_token_sim(t, u) for u in b) for t in a) / len(a)


def name_similarity(a: str, b: str) -> float:
    """Similarité 0 → 1 entre deux noms d'équipe.

    Le minimum des deux directions évite qu'un nom court « contenu » dans un autre
    gagne (« Milan » ≠ « Inter Milan », « Manchester City » ≠ « Manchester United »).
    """
    na, nb = normalize_team(a), normalize_team(b)
    na, nb = ALIASES.get(na, na), ALIASES.get(nb, nb)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    ta, tb = na.split(), nb.split()
    return min(_directional(ta, tb), _directional(tb, ta))


def best_match(name: str, candidates: Iterable[str]) -> Optional[str]:
    scored = sorted(((name_similarity(name, c), c) for c in candidates), reverse=True)
    if not scored or scored[0][0] < MIN_MATCH_SCORE:
        return None
    if len(scored) > 1 and scored[0][0] < 1.0 and scored[1][0] > scored[0][0] - 0.05:
        log.debug("Nom ambigu %r : %s", name, scored[:2])
        return None
    return scored[0][1]


# --- Modèle ---------------------------------------------------------------------------
@dataclass(frozen=True)
class GameResult:
    date: datetime
    home: bool
    opponent: str
    scored: float
    conceded: float
    competition: str

    @property
    def result(self) -> str:
        if self.scored > self.conceded:
            return "V"
        return "D" if self.scored < self.conceded else "N"


@dataclass
class TeamStats:
    name: str
    team_id: str
    sport: str                       # "soccer" ou "basketball"
    competition: str                 # compétition du classement (ex. eng.1)
    rank: Optional[int] = None
    table_size: Optional[int] = None
    played: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0
    scored: float = 0.0              # totaux du classement
    conceded: float = 0.0
    games: List[GameResult] = field(default_factory=list)  # matchs terminés, du plus récent au plus ancien
    injuries: List[str] = field(default_factory=list)
    league_strength: float = 1.0     # < 1 : championnat national plus faible (matchs de coupe d'Europe)
    european_rank: Optional[int] = None   # rang en phase de ligue UEFA (coupe d'Europe)
    european_size: Optional[int] = None

    @property
    def competition_name(self) -> str:
        return COMPETITION_NAMES.get(self.competition, self.competition)

    @property
    def is_soccer(self) -> bool:
        return self.sport == "soccer"

    @property
    def unit(self) -> str:
        return "buts" if self.is_soccer else "points"

    def _averages(self, games: Sequence[GameResult]) -> Tuple[Optional[float], Optional[float]]:
        if not games:
            return None, None
        return (sum(g.scored for g in games) / len(games), sum(g.conceded for g in games) / len(games))

    @property
    def avg_scored(self) -> Optional[float]:
        if len(self.games) >= 3:
            return self._averages(self.games)[0]
        return self.scored / self.played if self.played else None

    @property
    def avg_conceded(self) -> Optional[float]:
        if len(self.games) >= 3:
            return self._averages(self.games)[1]
        return self.conceded / self.played if self.played else None

    @property
    def diff_per_game(self) -> Optional[float]:
        if self.avg_scored is None or self.avg_conceded is None:
            return None
        return self.avg_scored - self.avg_conceded

    def last(self, n: int = 5) -> List[GameResult]:
        return self.games[:n]

    def last_averages(self, n: int = 5) -> Tuple[Optional[float], Optional[float]]:
        return self._averages(self.last(n))

    @property
    def form(self) -> str:
        """Forme des 5 derniers matchs, dans l'ordre chronologique (dernier match à droite)."""
        return "".join(g.result for g in reversed(self.last(5)))

    def _points_ratio(self, games: Sequence[GameResult]) -> Optional[float]:
        if not games:
            return None
        if self.is_soccer:
            return sum({"V": 3, "N": 1, "D": 0}[g.result] for g in games) / (3 * len(games))
        return sum(g.result == "V" for g in games) / len(games)

    @property
    def form_ratio(self) -> Optional[float]:
        return self._points_ratio(self.last(5))

    def venue_games(self, home: bool) -> List[GameResult]:
        return [g for g in self.games if g.home == home]

    def venue_ratio(self, home: bool) -> Optional[float]:
        games = self.venue_games(home)
        return self._points_ratio(games) if len(games) >= 2 else None

    def venue_record(self, home: bool) -> Tuple[int, int, int]:
        games = self.venue_games(home)
        return (sum(g.result == "V" for g in games), sum(g.result == "N" for g in games),
                sum(g.result == "D" for g in games))

    @property
    def rank_ratio(self) -> Optional[float]:
        if not self.rank or not self.table_size or self.table_size < 2:
            return None
        return 1 - (self.rank - 1) / (self.table_size - 1)

    @property
    def streak(self) -> Tuple[str, int]:
        if not self.games:
            return "", 0
        first = self.games[0].result
        count = 0
        for g in self.games:
            if g.result != first:
                break
            count += 1
        return first, count

    def last_game_before(self, moment: datetime) -> Optional[GameResult]:
        return next((g for g in self.games if g.date < moment), None)

    def scored_rate(self, n: int = 10) -> Optional[float]:
        """Part des n derniers matchs où l'équipe a marqué."""
        games = self.last(n)
        return sum(g.scored > 0 for g in games) / len(games) if games else None

    def conceded_rate(self, n: int = 10) -> Optional[float]:
        games = self.last(n)
        return sum(g.conceded > 0 for g in games) / len(games) if games else None

    @property
    def draw_ratio(self) -> Optional[float]:
        games = self.last(10)
        return sum(g.result == "N" for g in games) / len(games) if games else None


# --- Client ---------------------------------------------------------------------------
class StatsClient:
    def __init__(self, cache_dir: Path, session: Optional[requests.Session] = None,
                 ttl_hours: float = 24, timeout: float = 10.0):
        self.cache_dir = Path(cache_dir)
        self.session = session or requests.Session()
        self.ttl = ttl_hours * 3600
        self.timeout = timeout
        self._memo: Dict[str, Optional[dict]] = {}

    @staticmethod
    def supports(sport_key: str) -> bool:
        return sport_key in ESPN_LEAGUES

    # --- HTTP + cache -------------------------------------------------------------
    def _cache_path(self, url: str) -> Path:
        return self.cache_dir / f"{hashlib.sha1(url.encode()).hexdigest()}.json"

    def get_json(self, url: str, max_age: Optional[float] = None) -> Optional[dict]:
        """JSON d'une URL ESPN, depuis le cache s'il a moins de `max_age` secondes (24 h par défaut)."""
        ttl = self.ttl if max_age is None else max_age
        if url in self._memo:
            return self._memo[url]
        path = self._cache_path(url)
        cached = None
        if path.exists():
            try:
                cached = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                cached = None
        if cached and time.time() - cached.get("fetched", 0) < ttl:
            self._memo[url] = cached["data"]
            return cached["data"]
        data = None
        try:
            resp = self.session.get(url, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
            else:
                log.warning("ESPN HTTP %s : %s", resp.status_code, url)
        except (requests.RequestException, ValueError) as exc:
            log.warning("ESPN indisponible (%s) : %s", exc, url)
        if data is None and cached:
            data = cached["data"]  # cache expiré, mieux que rien
        elif data is not None:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"fetched": time.time(), "url": url, "data": data}), encoding="utf-8")
        self._memo[url] = data
        return data

    # --- Classement ------------------------------------------------------------------
    def standings(self, sport: str, league: str) -> Dict[str, dict]:
        """Nom ESPN → {id, rank, table_size, stats…} pour une compétition."""
        data = self.get_json(STANDINGS_URL.format(sport=sport, league=league)) or {}
        table: Dict[str, dict] = {}
        for child in data.get("children", []):
            entries = child.get("standings", {}).get("entries", [])
            for entry in entries:
                team = entry.get("team", {})
                values = {s.get("name"): s.get("value") for s in entry.get("stats", [])}
                rank = values.get("rank") or values.get("playoffSeed")
                table[team.get("displayName", "")] = {
                    "id": str(team.get("id", "")),
                    "rank": int(rank) if rank else None,
                    "table_size": len(entries),
                    "wins": int(values.get("wins") or 0),
                    "draws": int(values.get("ties") or 0),
                    "losses": int(values.get("losses") or 0),
                    "scored": float(values.get("pointsFor") or 0),
                    "conceded": float(values.get("pointsAgainst") or 0),
                }
        return table

    def _schedule(self, sport: str, league: str, team_id: str) -> List[Tuple[str, GameResult]]:
        data = self.get_json(SCHEDULE_URL.format(sport=sport, league=league, team_id=team_id)) or {}
        games: List[Tuple[str, GameResult]] = []
        for event in data.get("events", []):
            comp = (event.get("competitions") or [{}])[0]
            if not comp.get("status", {}).get("type", {}).get("completed"):
                continue
            sides = {c.get("homeAway"): c for c in comp.get("competitors", [])}
            ours = next((c for c in sides.values() if str(c.get("team", {}).get("id")) == team_id), None)
            theirs = next((c for c in sides.values() if c is not ours), None)
            if not ours or not theirs:
                continue
            try:
                date = datetime.fromisoformat(event["date"].replace("Z", "+00:00")).astimezone(timezone.utc)
                games.append((str(event.get("id")), GameResult(
                    date=date, home=ours.get("homeAway") == "home",
                    opponent=theirs.get("team", {}).get("displayName", "?"),
                    scored=_score(ours), conceded=_score(theirs), competition=league)))
            except (KeyError, TypeError, ValueError):
                continue
        return games

    def _competitions_of(self, sport: str, league: str, team_id: str) -> List[str]:
        if sport != "soccer":
            return [league]
        leagues = [league]
        others = DOMESTIC_SOCCER + EUROPEAN_SOCCER if league in EUROPEAN_SOCCER else EUROPEAN_SOCCER
        for other in others:
            if other != league and any(t["id"] == team_id for t in self.standings(sport, other).values()):
                leagues.append(other)
        return leagues

    def _injuries(self, sport: str, league: str, team_id: str) -> List[str]:
        if sport != "basketball":
            return []
        data = self.get_json(INJURIES_URL.format(sport=sport, league=league)) or {}
        for team in data.get("injuries", []):
            if str(team.get("id")) != team_id:
                continue
            out = []
            for inj in team.get("injuries", []):
                status = inj.get("status", "")
                if status in ("Out", "Day-To-Day", "Doubtful"):
                    detail = (inj.get("details") or {}).get("type") or ""
                    who = inj.get("athlete", {}).get("displayName", "?")
                    out.append(f"{who} ({status}{' — ' + detail if detail else ''})")
            return out
        return []

    # --- API publique -------------------------------------------------------------------
    def team_stats(self, sport_key: str, team_name: str) -> Optional[TeamStats]:
        if sport_key not in ESPN_LEAGUES:
            return None
        sport, league = ESPN_LEAGUES[sport_key]
        table = self.standings(sport, league)
        espn_name = best_match(team_name, table)
        if not espn_name:
            log.info("Équipe introuvable chez ESPN : %r (%s)", team_name, league)
            return None
        row = table[espn_name]
        competitions = self._competitions_of(sport, league, row["id"])
        seen: Dict[str, GameResult] = {}
        for comp in competitions:
            for event_id, game in self._schedule(sport, comp, row["id"]):
                seen.setdefault(event_id, game)
        games = sorted(seen.values(), key=lambda g: g.date, reverse=True)
        # Coupe d'Europe : classement et bilan du championnat national, pondérés par sa force.
        ranking_league, ranking_row, strength, euro = league, row, 1.0, (None, None)
        if league in EUROPEAN_SOCCER:
            domestic = next((c for c in competitions if c in DOMESTIC_LEAGUES), None)
            if domestic:
                dom_row = next(t for t in self.standings(sport, domestic).values() if t["id"] == row["id"])
                ranking_league, ranking_row, strength = domestic, dom_row, DOMESTIC_LEAGUES[domestic][1]
                euro = (row["rank"], row["table_size"])
        return TeamStats(
            name=espn_name, team_id=row["id"], sport=sport, competition=ranking_league,
            rank=ranking_row["rank"], table_size=ranking_row["table_size"],
            played=ranking_row["wins"] + ranking_row["draws"] + ranking_row["losses"],
            wins=ranking_row["wins"], draws=ranking_row["draws"], losses=ranking_row["losses"],
            scored=ranking_row["scored"], conceded=ranking_row["conceded"], games=games,
            injuries=self._injuries(sport, league, row["id"]),
            league_strength=strength, european_rank=euro[0], european_size=euro[1],
        )

    def match_stats(self, sport_key: str, home: str, away: str) -> Tuple[Optional[TeamStats], Optional[TeamStats]]:
        if sport_key not in ESPN_LEAGUES:
            return None, None
        return self.team_stats(sport_key, home), self.team_stats(sport_key, away)


def _score(competitor: dict) -> float:
    score = competitor.get("score")
    if isinstance(score, dict):
        score = score.get("value", score.get("displayValue"))
    return float(score)
