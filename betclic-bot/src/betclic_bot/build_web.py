"""Génère le site statique public (GitHub Pages) dans `docs/` à partir du grand livre.

Le site est une page unique : les données sont injectées dans `index.html` (balise JSON),
la mise en forme et l'interactivité viennent de `style.css` et `app.js` (copiés depuis `web/`).
"""
from __future__ import annotations

import json
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List
from zoneinfo import ZoneInfo

from . import rules
from .ledger import PENDING, Ledger, parse_iso
from .models import MARKET_LABELS

WEB_DIR = Path(__file__).parent / "web"
PROFILE_NAMES = {"SAFE": "Safe", "SWEET_SPOT": "Sweet Spot", "AUDACIEUX": "Audacieux", "COMBINE": "Combiné"}


def _local(value: str, tz: ZoneInfo) -> datetime:
    return parse_iso(value).astimezone(tz)


def _group(bets: List[dict], key) -> List[dict]:
    groups: Dict[str, List[dict]] = defaultdict(list)
    for bet in bets:
        groups[key(bet)].append(bet)
    rows = []
    for name, items in groups.items():
        settled = [b for b in items if b["status"] != PENDING]
        won = sum(b["status"] == "GAGNE" for b in settled)
        lost = sum(b["status"] == "PERDU" for b in settled)
        staked = round(sum(b["stake"] for b in settled if b["status"] != "REMBOURSE"), 2)
        net = round(sum(b["profit"] for b in settled), 2)
        rows.append({"name": name, "count": len(items), "settled": len(settled), "won": won, "lost": lost,
                     "winrate": won / (won + lost) if won + lost else None, "staked": staked, "net": net,
                     "yield": net / staked if staked else None})
    return sorted(rows, key=lambda r: (-r["count"], r["name"]))


def site_data(ledger: Ledger, now: datetime, tz: str = "Europe/Paris", site_url: str = "") -> dict:
    zone = ZoneInfo(tz)
    m = ledger.metrics()
    today = now.astimezone(zone).strftime("%Y-%m-%d")
    last_balance: Dict[str, float] = {}
    for op in ledger.operations:
        if op.get("bet_id"):
            last_balance[op["bet_id"]] = op["balance"]

    bets = []
    for bet in sorted(ledger.bets.values(), key=lambda b: b["placed_at"], reverse=True):
        placed = _local(bet["placed_at"], zone)
        bets.append({
            "id": bet["id"], "kind": bet["kind"], "profile": bet["profile"],
            "profile_name": PROFILE_NAMES.get(bet["profile"], bet["profile"]),
            "placed": placed.strftime("%d/%m"), "placed_day": placed.strftime("%Y-%m-%d"),
            "kickoff": _local(bet["kickoff"], zone).strftime("%d/%m %H:%M"),
            "competition": bet["competition"], "match": bet["match"], "market": bet["market_label"],
            "selection": bet["selection"], "odd": bet["odd"], "stake": bet["stake"],
            "potential": bet["potential_payout"], "status": bet["status"], "score": bet.get("final_score"),
            "net": bet["profit"], "balance": last_balance.get(bet["id"]), "confidence": bet["score"],
            "headline": bet.get("headline", ""), "estimated": bet.get("estimated", False),
            "legs": [{"match": l["match"], "competition": l["competition"], "selection": l["selection"],
                      "odd": l["odd"], "kickoff": _local(l["kickoff"], zone).strftime("%d/%m %H:%M"),
                      "status": l.get("status", PENDING), "score": l.get("final_score")} for l in bet["legs"]],
        })

    equity = []
    for date, value, bet in ledger.equity_series():
        point = {"t": _local(date, zone).strftime("%d/%m %H:%M"), "v": value}
        if bet:
            point.update(label=bet["label"], status=bet["status"], net=bet["profit"], score=bet.get("final_score"))
        else:
            point.update(label="Capital de départ", status=None, net=None, score=None)
        equity.append(point)

    all_bets = list(ledger.bets.values())
    return {
        "generated_at": now.astimezone(zone).strftime("%d/%m/%Y à %H:%M"),
        "today": now.astimezone(zone).strftime("%d/%m/%Y"),
        "started": _local(ledger.data["created_at"], zone).strftime("%d/%m/%Y"),
        "site_url": site_url,
        "metrics": {
            "initial": m.initial, "equity": m.equity, "balance": m.balance, "exposure": m.exposure,
            "profit": m.profit, "profit_pct": m.profit / m.initial, "roi": m.roi, "yield": m.yield_,
            "winrate": m.winrate, "won": m.won, "lost": m.lost, "void": m.void, "pending": m.pending,
            "max_drawdown": m.max_drawdown, "max_drawdown_pct": m.max_drawdown_pct,
            "staked_today": ledger.staked_on(today, tz), "daily_cap": rules.DAILY_EXPOSURE_MAX,
        },
        "equity": equity,
        "positions": [b for b in bets if b["status"] == PENDING],
        "bets": bets,
        "analytics": {
            "by_profile": _group(all_bets, lambda b: PROFILE_NAMES.get(b["profile"], b["profile"])),
            "by_market": _group(all_bets, lambda b: "Combiné" if b["kind"] == "COMBINE"
                                else MARKET_LABELS.get(b["market"], b["market"])),
        },
        "rules": {"stake_pct": {PROFILE_NAMES[k]: v for k, v in rules.STAKE_PCT.items()},
                  "stake_min": rules.STAKE_MIN, "daily_cap": rules.DAILY_EXPOSURE_MAX},
    }


def build(ledger: Ledger, out_dir: Path, now: datetime | None = None, tz: str = "Europe/Paris",
          site_url: str = "") -> Path:
    """Écrit `docs/index.html`, `docs/style.css`, `docs/app.js` et `docs/.nojekyll`."""
    now = now or datetime.now(timezone.utc)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    data = json.dumps(site_data(ledger, now, tz, site_url), ensure_ascii=False).replace("</", "<\\/")
    html = (WEB_DIR / "index.html").read_text(encoding="utf-8").replace("__FUND_DATA__", data)
    (out_dir / "index.html").write_text(html, encoding="utf-8")
    for asset in ("style.css", "app.js"):
        shutil.copyfile(WEB_DIR / asset, out_dir / asset)
    (out_dir / ".nojekyll").write_text("", encoding="utf-8")
    return out_dir / "index.html"
