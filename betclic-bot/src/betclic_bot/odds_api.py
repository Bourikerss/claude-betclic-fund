"""Client minimal pour The Odds API v4."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Tuple

import requests

from . import rules

BASE_URL = "https://api.the-odds-api.com/v4"
log = logging.getLogger(__name__)


class OddsApiError(RuntimeError):
    def __init__(self, message: str, status: Optional[int] = None, code: Optional[str] = None):
        super().__init__(message)
        self.status = status
        self.code = code


class QuotaExhausted(OddsApiError):
    pass


def _int_header(headers: Mapping[str, str], name: str) -> Optional[int]:
    value = headers.get(name)
    try:
        return int(float(value)) if value is not None else None
    except ValueError:
        return None


@dataclass(frozen=True)
class QuotaInfo:
    remaining: Optional[int] = None
    used: Optional[int] = None
    last_cost: Optional[int] = None

    @classmethod
    def from_headers(cls, headers: Mapping[str, str]) -> "QuotaInfo":
        return cls(
            remaining=_int_header(headers, "x-requests-remaining"),
            used=_int_header(headers, "x-requests-used"),
            last_cost=_int_header(headers, "x-requests-last"),
        )


def iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class OddsApiClient:
    def __init__(self, api_key: str, session: Optional[requests.Session] = None,
                 base_url: str = BASE_URL, timeout: float = 20.0):
        if not api_key:
            raise ValueError("ODDS_API_KEY manquant (voir betclic-bot/.env.example)")
        self.api_key = api_key
        self.session = session or requests.Session()
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Tuple[Any, QuotaInfo]:
        query = {"apiKey": self.api_key, **(params or {})}
        try:
            resp = self.session.get(f"{self.base_url}{path}", params=query, timeout=self.timeout)
        except requests.RequestException as exc:
            raise OddsApiError(f"Erreur réseau sur {path} : {exc}") from exc

        quota = QuotaInfo.from_headers(resp.headers)
        if resp.status_code == 200:
            return resp.json(), quota

        try:
            payload = resp.json()
        except ValueError:
            payload = {}
        code = payload.get("error_code")
        message = payload.get("message") or resp.text[:200]
        if code == "OUT_OF_USAGE_CREDITS" or (resp.status_code == 401 and quota.remaining == 0):
            raise QuotaExhausted(f"Quota The Odds API épuisé : {message}", resp.status_code, code)
        raise OddsApiError(f"HTTP {resp.status_code} sur {path} : {message}", resp.status_code, code)

    def get_sports(self) -> Tuple[List[dict], QuotaInfo]:
        """Liste des sports en saison — gratuit."""
        return self._get("/sports")

    def get_events(self, sport_key: str, start: datetime, end: datetime) -> Tuple[List[dict], QuotaInfo]:
        """Matchs à venir sans cotes — gratuit."""
        return self._get(
            f"/sports/{sport_key}/events",
            {"commenceTimeFrom": iso_z(start), "commenceTimeTo": iso_z(end), "dateFormat": "iso"},
        )

    def get_odds(self, sport_key: str, start: datetime, end: datetime) -> Tuple[List[dict], QuotaInfo]:
        """Cotes Pinnacle + Betclic — coûte 1 crédit par marché demandé (`rules.markets_for`)."""
        return self._get(
            f"/sports/{sport_key}/odds",
            {
                "regions": rules.REGIONS,
                "bookmakers": ",".join(rules.BOOKMAKERS),
                "markets": ",".join(rules.markets_for(sport_key)),
                "oddsFormat": "decimal",
                "dateFormat": "iso",
                "commenceTimeFrom": iso_z(start),
                "commenceTimeTo": iso_z(end),
            },
        )
