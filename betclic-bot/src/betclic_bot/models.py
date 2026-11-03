"""Modèle de données d'une opportunité retenue par l'analyste."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Optional, Tuple

if TYPE_CHECKING:
    from .stats_client import TeamStats

MARKET_LABELS = {
    "h2h": "Vainqueur du match",
    "totals": "Total de buts (Plus/Moins)",
    "spreads": "Handicap",
    "double_chance": "Double chance",
    "dnb": "Remboursé si nul",
    "btts": "Les deux équipes marquent",
    "team_totals": "Buts d'une équipe",
}

MARKET_SHORT = {"h2h": "Vainqueur", "totals": "Total", "spreads": "Handicap", "double_chance": "Double chance",
                "dnb": "Remboursé si nul", "btts": "BTTS", "team_totals": "Buts équipe"}


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


PROFILE_BADGES = {
    "SAFE": "🛡️ SAFE",
    "SWEET_SPOT": "🎯 SWEET SPOT",
    "AUDACIEUX": "🔥 AUDACIEUX",
}
PROFILE_LABELS = {
    "SAFE": "Safe (Base solide)",
    "SWEET_SPOT": "Sweet Spot (Équilibre cote / sécurité)",
    "AUDACIEUX": "Audacieux / Value (belle cote)",
}


@dataclass(frozen=True)
class Opportunity:
    event_id: str
    sport_key: str
    sport: str
    ligue: str
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
    profile: str
    score: int                      # Score d'Opportunité /100
    score_market: float             # pilier 1 : réalité du marché
    score_price: float              # pilier 2 : compétitivité de la cote Betclic
    score_stats: float              # pilier 3 : convergence statistique
    stats_convergence: Optional[float]  # 0 → 1, None si stats indisponibles
    estimated: bool                 # cote Betclic estimée (marché dérivé, modèle de Poisson)
    min_odd: Optional[float]        # cote minimale à exiger sur Betclic (marchés dérivés)
    headline: str                   # 1 phrase : la stat clé qui justifie ce marché
    stake: float                    # mise conseillée (plancher MIN_STAKE appliqué)
    stake_pct: float                # % théorique du profil
    stake_theoretical: float        # bankroll × % du profil, avant plancher
    arguments: Tuple[str, ...] = ()
    vigilance: Tuple[str, ...] = ()      # risque principal en premier
    key_stats: Tuple[str, ...] = ()      # 2–3 stats pour Telegram
    home_stats: Optional["TeamStats"] = field(default=None, compare=False)
    away_stats: Optional["TeamStats"] = field(default=None, compare=False)

    @property
    def match(self) -> str:
        return f"{self.home_team} vs {self.away_team}"

    @property
    def fair_odd(self) -> float:
        return 1.0 / self.fair_prob

    @property
    def market_label(self) -> str:
        return MARKET_LABELS.get(self.market, self.market)

    @property
    def odd_to_take(self) -> float:
        """Cote à afficher : la vraie cote Betclic, ou la cote minimale à exiger si elle est estimée."""
        return self.min_odd if self.estimated and self.min_odd else self.betclic_odd

    @property
    def stake_floored(self) -> bool:
        return self.stake > self.stake_theoretical

    @property
    def badge(self) -> str:
        return PROFILE_BADGES.get(self.profile, self.profile)

    @property
    def bet_id(self) -> str:
        point = "" if self.point is None else f"_{self.point:+g}"
        return f"{self.event_id}_{self.market}_{slugify(self.outcome_name)}{point}"
