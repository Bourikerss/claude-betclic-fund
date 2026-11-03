"""Configuration chargée depuis betclic-bot/.env."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from . import rules
from .devig import METHODS

BOT_ROOT = Path(__file__).resolve().parents[2]


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


@dataclass(frozen=True)
class Settings:
    odds_api_key: str
    telegram_token: str
    telegram_chat_id: str
    vault_path: Path
    state_path: Path
    stats_cache_path: Path
    ledger_path: Path
    site_url: str
    bankroll_override: Optional[float]
    default_bankroll: float
    monthly_credits: int
    credit_reserve: int
    runs_per_day: int
    max_sports_per_run: int
    lookahead_hours: int
    devig_method: str
    timezone: str

    @classmethod
    def from_env(cls, env_file: Optional[Path] = None) -> "Settings":
        load_dotenv(env_file or BOT_ROOT / ".env")
        method = _env("DEVIG_METHOD", "multiplicative")
        if method not in METHODS:
            raise ValueError(f"DEVIG_METHOD invalide : {method!r} (attendu : {METHODS})")
        override = _env("BANKROLL")
        return cls(
            odds_api_key=_env("ODDS_API_KEY"),
            telegram_token=_env("TELEGRAM_BOT_TOKEN"),
            telegram_chat_id=_env("TELEGRAM_CHAT_ID"),
            vault_path=Path(_env("VAULT_PATH") or BOT_ROOT.parent).expanduser(),
            state_path=Path(_env("STATE_PATH") or BOT_ROOT / "data" / "quota_state.json").expanduser(),
            stats_cache_path=Path(_env("STATS_CACHE_PATH") or BOT_ROOT / "data" / "espn_cache").expanduser(),
            ledger_path=Path(_env("LEDGER_PATH") or BOT_ROOT / "data" / "ledger.json").expanduser(),
            site_url=_env("SITE_URL"),  # vide : déduite du remote GitHub
            bankroll_override=float(override) if override else None,
            default_bankroll=float(_env("DEFAULT_BANKROLL", "1000")),
            monthly_credits=int(_env("MONTHLY_CREDITS", str(rules.MONTHLY_CREDITS))),
            credit_reserve=int(_env("CREDIT_RESERVE", "30")),
            runs_per_day=int(_env("RUNS_PER_DAY", "2")),
            max_sports_per_run=int(_env("MAX_SPORTS_PER_RUN", "10")),
            lookahead_hours=int(_env("LOOKAHEAD_HOURS", "48")),
            devig_method=method,
            timezone=_env("TIMEZONE", "Europe/Paris"),
        )
