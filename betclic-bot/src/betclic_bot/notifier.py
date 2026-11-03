"""Notification Telegram (Bot API, parse_mode HTML) : un seul message par jour, lisible en 3 secondes."""
from __future__ import annotations

import logging
import re
from datetime import datetime
from html import escape
from typing import Optional, Sequence
from zoneinfo import ZoneInfo

import requests

from .ledger import Metrics

log = logging.getLogger(__name__)
API_URL = "https://api.telegram.org/bot{token}/sendMessage"
MAX_MESSAGE_CHARS = 4000  # limite Telegram : 4096
_DAYS = ("lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim.")
BADGES = {"SAFE": "🛡️", "SWEET_SPOT": "🎯", "AUDACIEUX": "🔥", "COMBINE": "🧩"}


def _plain(text: str) -> str:
    """Retire le gras Markdown des textes partagés avec les fiches Obsidian."""
    return re.sub(r"\*\*(.+?)\*\*", r"\1", text)


def _num(x: float) -> str:
    return f"{x:.2f}".replace(".", ",")


def _signed(x: float) -> str:
    return ("+" if x >= 0 else "−") + _num(abs(x))


def _pct(ratio: float) -> str:
    return f"{ratio * 100:+.1f}".replace(".", ",").replace("-", "−")


def _when(kickoff: str, tz: str) -> str:
    local = datetime.fromisoformat(kickoff.replace("Z", "+00:00")).astimezone(ZoneInfo(tz))
    return f"{_DAYS[local.weekday()]} {local:%Hh%M}"


def format_bet(bet: dict, tz: str = "Europe/Paris") -> str:
    """Pari simple : 3 lignes (match, pari, stat clé)."""
    e = escape
    badge = "🎲" if bet["kind"] == "FUN" else BADGES.get(bet["profile"], "•")
    return "\n".join([
        f"{badge} <b>{e(bet['match'])}</b> ({e(bet['competition'])} · {_when(bet['kickoff'], tz)})",
        f"👉 <b>{e(bet['selection'])}</b> @ <b>{_num(bet['odd'])}</b> — Mise : <b>{_num(bet['stake'])} €</b>",
        f"📊 <i>{e(_plain(bet.get('headline') or ''))}</i>",
    ])


def format_combo(bet: dict) -> str:
    e = escape
    lines = [f"🧩 <b>COMBINÉ DU JOUR</b> @ <b>{_num(bet['odd'])}</b> — Mise : <b>{_num(bet['stake'])} €</b>"]
    lines += [f"• {e(leg['match'])} : <b>{e(leg['selection'])}</b> (@ {_num(leg['odd'])})" for leg in bet["legs"]]
    return "\n".join(lines)


def format_daily(metrics: Metrics, settled: Sequence[dict], singles: Sequence[dict], combo: Optional[dict],
                 site_url: str, tz: str = "Europe/Paris") -> str:
    """Message quotidien unique : portefeuille, bilan de la veille, paris du jour, lien du site."""
    won = sum(b["status"] == "GAGNE" for b in settled)
    lost = sum(b["status"] == "PERDU" for b in settled)
    yesterday = round(sum(b["profit"] for b in settled), 2)
    parts = [
        f"💰 <b>PORTEFEUILLE CLAUDE : {_num(metrics.equity)} €</b> "
        f"({_signed(metrics.profit)} € | ROI : {_pct(metrics.roi)} %)",
        f"📅 <i>Hier : {won}G - {lost}P ({_signed(yesterday)} €)</i>",
        "",
        "🎯 <b>LES PARIS DU JOUR</b>",
    ]
    if not singles and not combo:
        parts.append("<i>Aucun pari aujourd'hui : rien ne passe les filtres.</i>")
    for bet in singles:
        parts += ["", format_bet(bet, tz)]
    if combo:
        parts += ["", format_combo(combo) if combo["kind"] == "COMBINE" else "🎲 <b>PARI FUN DU JOUR</b>\n" + format_bet(combo, tz)]
    parts += ["", f"🌐 <b>Suivi en direct :</b> {escape(site_url)}"]
    return "\n".join(parts)[:MAX_MESSAGE_CHARS]


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str, session: Optional[requests.Session] = None, timeout: float = 10.0):
        self.token = token
        self.chat_id = chat_id
        self.session = session or requests.Session()
        self.timeout = timeout

    @property
    def enabled(self) -> bool:
        return bool(self.token and self.chat_id)

    def send(self, text: str) -> bool:
        if not self.enabled:
            log.info("Telegram non configuré — message non envoyé")
            return False
        try:
            resp = self.session.post(
                API_URL.format(token=self.token),
                json={"chat_id": self.chat_id, "text": text, "parse_mode": "HTML",
                      "disable_web_page_preview": True},
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            log.error("Échec d'envoi Telegram : %s", exc)
            return False
        if resp.status_code != 200:
            log.error("Telegram HTTP %s : %s", resp.status_code, resp.text[:200])
            return False
        return True
