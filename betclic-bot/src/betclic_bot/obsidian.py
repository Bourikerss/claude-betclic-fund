"""Écriture des fiches d'analyse dans le coffre Obsidian."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple
from zoneinfo import ZoneInfo

import yaml

from . import rules
from .models import MARKET_SHORT, PROFILE_LABELS, Opportunity, slugify
from .stats_client import TeamStats

log = logging.getLogger(__name__)

BETS_DIR = "02 - Paris Détectés"
BILAN_DIR = "03 - Bilan & Bankroll"
HUBS_DIR = "04 - Sports & Ligues"
BANKROLL_NOTE = f"{BILAN_DIR}/Bankroll.md"
HISTORY_HEADING = "## Historique des cotes"
STRATEGY_NOTE = "Stratégie Analyste Contextuel"

_FORBIDDEN = re.compile(r'[\\/:*?"<>|#^\[\]]')


def safe_filename(name: str) -> str:
    return re.sub(r"\s+", " ", _FORBIDDEN.sub("-", name)).strip()[:180]


def split_frontmatter(text: str) -> Tuple[dict, str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    meta = yaml.safe_load(text[4:end]) or {}
    body = text[end + 4:].lstrip("\n")
    return (meta if isinstance(meta, dict) else {}), body


def render_note(meta: dict, body: str) -> str:
    dumped = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True, default_flow_style=None, width=1000)
    return f"---\n{dumped}---\n\n{body}"


def _fmt(dt: datetime, tz: ZoneInfo) -> str:
    return dt.astimezone(tz).strftime("%Y-%m-%dT%H:%M")


@dataclass(frozen=True)
class UpsertResult:
    path: Path
    created: bool
    updated: bool


class ObsidianVault:
    def __init__(self, root: Path, timezone: str = "Europe/Paris"):
        self.root = Path(root)
        self.tz = ZoneInfo(timezone)
        self._index: Optional[Dict[str, Path]] = None

    @property
    def bets_dir(self) -> Path:
        return self.root / BETS_DIR

    # --- lecture ---------------------------------------------------------------
    def iter_bets(self) -> Iterator[Tuple[Path, dict, str]]:
        if not self.bets_dir.exists():
            return
        for path in sorted(self.bets_dir.glob("*.md")):
            meta, body = split_frontmatter(path.read_text(encoding="utf-8"))
            if meta.get("type") == "pari":
                yield path, meta, body

    def _bet_index(self) -> Dict[str, Path]:
        if self._index is None:
            self._index = {str(m["id"]): p for p, m, _ in self.iter_bets() if m.get("id")}
        return self._index

    def has_bet(self, bet_id: str) -> bool:
        path = self._bet_index().get(bet_id)
        return bool(path and path.exists())

    # --- écriture ---------------------------------------------------------------
    def upsert_bet(self, bet: Opportunity, bankroll: float, now: datetime) -> UpsertResult:
        index = self._bet_index()
        existing = index.get(bet.bet_id)
        if existing and existing.exists():
            return self._update(existing, bet, now)

        self.bets_dir.mkdir(parents=True, exist_ok=True)
        local_day = bet.commence_time.astimezone(self.tz).strftime("%Y-%m-%d")
        base = safe_filename(f"{local_day} - {bet.match} - {bet.selection} ({MARKET_SHORT.get(bet.market, bet.market)})")
        path = self.bets_dir / f"{base}.md"
        if path.exists():
            path = self.bets_dir / f"{base} {slugify(bet.bet_id)[-8:]}.md"

        path.write_text(render_note(self._frontmatter(bet, bankroll, now), self._body(bet, now)), encoding="utf-8")
        index[bet.bet_id] = path
        self.ensure_hubs(bet)
        log.info("Nouvelle fiche : %s", path.name)
        return UpsertResult(path, created=True, updated=False)

    def _update(self, path: Path, bet: Opportunity, now: datetime) -> UpsertResult:
        meta, body = split_frontmatter(path.read_text(encoding="utf-8"))
        if meta.get("statut") != rules.STATUT_EN_ATTENTE:
            return UpsertResult(path, created=False, updated=False)

        ev_pct = round(bet.ev * 100, 2)
        changed = meta.get("cote_betclic_actuelle") != bet.betclic_odd or meta.get("ev_actuel_percent") != ev_pct
        meta["cote_betclic_actuelle"] = bet.betclic_odd
        meta["ev_actuel_percent"] = ev_pct
        meta["derniere_maj"] = _fmt(now, self.tz)
        if changed:
            body = self._append_history(body, self._history_line(bet, now))
        path.write_text(render_note(meta, body), encoding="utf-8")
        return UpsertResult(path, created=False, updated=changed)

    def _frontmatter(self, bet: Opportunity, bankroll: float, now: datetime) -> dict:
        ev_pct = round(bet.ev * 100, 2)
        return {
            # --- clés obligatoires (CLAUDE.md §5) ---
            "sport": bet.sport,
            "ligue": bet.ligue,
            "match": bet.match,
            "date": _fmt(bet.commence_time, self.tz),
            "marche": bet.market_label,
            "selection": bet.selection,
            "profil": bet.profile,
            "score_confiance": bet.score,
            # Marché dérivé : cote minimale à exiger (la cote réelle se note dans `cote_prise`).
            "cote_betclic": bet.odd_to_take,
            "fair_odd_pinnacle": round(bet.fair_odd, 3),
            "probabilite_reelle": round(bet.fair_prob * 100, 2),
            "ev_percent": ev_pct,
            "mise_recommandee": bet.stake,
            "statut": rules.STATUT_EN_ATTENTE,
            "profit": 0,
            # --- compléments ---
            "type": "pari",
            "id": bet.bet_id,
            "type_marche": bet.market,
            "cote_source": "estimee" if bet.estimated else "betclic",
            "cote_estimee": round(bet.betclic_odd, 2) if bet.estimated else None,
            "mise_percent": round(bet.stake_pct * 100, 2),
            "mise_theorique": bet.stake_theoretical,
            "score_marche": bet.score_market,
            "score_cote": bet.score_price,
            "score_stats": bet.score_stats,
            "convergence_stats": bet.stats_convergence,
            "cote_pinnacle": bet.pinnacle_odd,
            "marge_pinnacle_percent": round((bet.pinnacle_overround - 1) * 100, 2),
            "marge_betclic_percent": round((bet.betclic_overround - 1) * 100, 2),
            "bankroll_reference": bankroll,
            "cote_betclic_actuelle": bet.betclic_odd,
            "ev_actuel_percent": ev_pct,
            "detecte_le": _fmt(now, self.tz),
            "derniere_maj": _fmt(now, self.tz),
            "sport_key": bet.sport_key,
            "event_id": bet.event_id,
            "liens": [f"[[{bet.sport}]]", f"[[{bet.ligue}]]"],
            "tags": ["pari", slugify(bet.sport), f"profil/{bet.profile.lower()}"],
        }

    def _history_line(self, bet: Opportunity, now: datetime) -> str:
        odd = f"≈ {bet.betclic_odd:.2f} (estimée, minimum {bet.min_odd})" if bet.estimated else f"**{bet.betclic_odd}**"
        return (f"- {now.astimezone(self.tz):%d/%m %H:%M} — Betclic {odd} · "
                f"fair {bet.fair_odd:.3f} · EV {bet.ev * 100:+.2f} %")

    @staticmethod
    def _append_history(body: str, line: str) -> str:
        start = body.find(HISTORY_HEADING)
        if start == -1:
            return body.rstrip("\n") + f"\n\n{HISTORY_HEADING}\n{line}\n"
        nxt = body.find("\n## ", start + len(HISTORY_HEADING))
        if nxt == -1:
            return body.rstrip("\n") + f"\n{line}\n"
        return body[:nxt].rstrip("\n") + f"\n{line}\n" + body[nxt:]

    def _context(self, bet: Opportunity) -> str:
        home, away = bet.home_stats, bet.away_stats
        if home is None or away is None:
            return ("> [!note] Statistiques indisponibles\n"
                    "> ESPN ne couvre pas cette compétition (ou une équipe n'a pas été reconnue) : "
                    "l'analyse repose sur les cotes seules.\n")
        unit = home.unit

        def avg(v: Optional[float]) -> str:
            return "—" if v is None else f"{v:.2f}"

        def record(t: TeamStats) -> str:
            return f"{t.wins}V-{t.draws}N-{t.losses}D" if t.is_soccer else f"{t.wins}V-{t.losses}D"

        def venue(t: TeamStats, is_home: bool) -> str:
            w, d, l = t.venue_record(is_home)
            return f"{w}V-{d}N-{l}D" if t.is_soccer else f"{w}V-{l}D"

        def streak(t: TeamStats) -> str:
            result, count = t.streak
            word = {"V": "victoire", "D": "défaite", "N": "nul"}.get(result, "")
            return f"{count} {word}{'s' if count > 1 else ''}" if count else "—"

        def rank(t: TeamStats) -> str:
            return f"{t.rank}/{t.table_size} · {t.competition_name}" if t.rank else "—"

        def euro(t: TeamStats) -> str:
            return f"{t.european_rank}/{t.european_size}" if t.european_rank else "—"

        rows = [
            ("Classement", rank(home), rank(away)),
            *([("Phase de ligue UEFA", euro(home), euro(away))] if home.european_rank or away.european_rank else []),
            ("Bilan saison", record(home), record(away)),
            ("Forme (5 derniers, dernier à droite)", f"`{home.form or '—'}`", f"`{away.form or '—'}`"),
            ("Série en cours", streak(home), streak(away)),
            ("Domicile (dom.) / Extérieur (ext.)", f"dom. {venue(home, True)}", f"ext. {venue(away, False)}"),
            (f"{unit.capitalize()} marqués / match", avg(home.avg_scored), avg(away.avg_scored)),
            (f"{unit.capitalize()} encaissés / match", avg(home.avg_conceded), avg(away.avg_conceded)),
            ("Différence / match", avg(home.diff_per_game), avg(away.diff_per_game)),
            ("Absents / incertains", ", ".join(home.injuries[:4]) or "—", ", ".join(away.injuries[:4]) or "—"),
        ]
        lines = [f"| | {bet.home_team} | {bet.away_team} |", "|---|---|---|"]
        lines += [f"| {label} | {h} | {a} |" for label, h, a in rows]
        for team in (home, away):
            lines.append(f"\n**Derniers matchs — {team.name}**")
            for g in team.last(5):
                where = "dom." if g.home else "ext."
                lines.append(f"- {g.date.astimezone(self.tz):%d/%m} · {g.opponent} ({where}) "
                             f"{g.scored:g}-{g.conceded:g} **{g.result}**")
            if not team.games:
                lines.append("- aucun match terminé cette saison")
        lines.append("\n*Source : ESPN (classement et calendrier, cache 24 h).*")
        return "\n".join(lines) + "\n"

    @staticmethod
    def _odds_rows(bet: Opportunity) -> str:
        if not bet.estimated:
            return f"| Cote Betclic | **{bet.betclic_odd}** |\n| Cote Pinnacle (brute) | {bet.pinnacle_odd} |"
        source = "1N2 Pinnacle" if bet.market in ("double_chance", "dnb") else "modèle de Poisson calé sur Pinnacle"
        return (f"| Cote minimale à exiger sur Betclic | **{bet.min_odd}** |\n"
                f"| Cote Betclic estimée | ≈ {bet.betclic_odd:.2f} (non publiée via l'API) |\n"
                f"| Source de la probabilité | {source} |")

    @staticmethod
    def _stake_lines(bet: Opportunity) -> str:
        label = PROFILE_LABELS.get(bet.profile, bet.profile)
        return (f"- Mise engagée : **{bet.stake:.2f} €** — profil **{label}** : {bet.stake_pct * 100:g} % du solde "
                f"({bet.stake_theoretical:.2f} € théoriques, plancher {rules.STAKE_MIN:.2f} €).")

    def _body(self, bet: Opportunity, now: datetime) -> str:
        detected = now.astimezone(self.tz).strftime("%d/%m/%Y à %H:%M")
        kickoff = bet.commence_time.astimezone(self.tz).strftime("%d/%m/%Y %H:%M")
        arguments = "\n".join(f"- {a}" for a in bet.arguments)
        main_risk, *other_risks = bet.vigilance or ("Aucun signal d'alerte particulier",)
        others = "".join(f"\n> - {r}" for r in other_risks)
        stats_txt = "indisponibles" if bet.stats_convergence is None else f"{bet.stats_convergence * 100:.0f} %"
        return f"""# {bet.badge} — {bet.match} : {bet.selection}

> [!info] Analyse générée le {detected}
> **Profil** : {PROFILE_LABELS.get(bet.profile, bet.profile)} · **Score d'Opportunité** : **{bet.score}/100**
> **Sport** : [[{bet.sport}]] · **Ligue** : [[{bet.ligue}]] · **Méthode** : [[{STRATEGY_NOTE}]] · [[Profils de risque]]
> **Coup d'envoi** : {kickoff}

## 🎯 Le pari

| Indicateur | Valeur |
|---|---|
| Marché | {bet.market_label} |
| Sélection | **{bet.selection}** |
{self._odds_rows(bet)}
| Cote juste Pinnacle (sans marge) | {bet.fair_odd:.3f} |
| Probabilité réelle | {bet.fair_prob * 100:.2f} % |
| Expected Value{" (estimée)" if bet.estimated else ""} | {bet.ev * 100:+.2f} % |
| Marge Betclic {"(1N2 du match)" if bet.estimated else "sur ce marché"} | {(bet.betclic_overround - 1) * 100:.2f} % |

**[[Score d'Opportunité]] : {bet.score}/100** = marché {bet.score_market:g}/35 + cote {bet.score_price:g}/35 + stats {bet.score_stats:g}/30 (convergence {stats_txt})

## 📊 Contexte sportif

{self._context(bet)}
## 🧠 Argumentaire du pronostic

{arguments}

## ⚠️ Point de vigilance

> [!warning] {main_risk}{others}

## 💰 Gestion de mise

{self._stake_lines(bet)}
- Gain potentiel : **{bet.stake * bet.odd_to_take:.2f} €** (cote engagée {bet.odd_to_take:.2f}).
- Paper trading : mise débitée du [[Bankroll|Fonds Claude]] (grand livre `betclic-bot/data/ledger.json`).

{HISTORY_HEADING}
{self._history_line(bet, now)}

## Suivi

- Réglé automatiquement par `auto_settle` (score final ESPN) au run quotidien suivant le match :
  `statut`, `profit` et `score_final` sont mis à jour ici et au grand livre.

## Notes personnelles

"""

    def ensure_hubs(self, bet: Opportunity) -> None:
        """Crée les notes hub [[Sport]] et [[Ligue]] si elles n'existent pas."""
        hubs = self.root / HUBS_DIR
        hubs.mkdir(parents=True, exist_ok=True)
        sport_note = hubs / f"{safe_filename(bet.sport)}.md"
        if not sport_note.exists():
            sport_note.write_text(render_note(
                {"type": "sport", "tags": ["hub/sport"]},
                f"""# {bet.sport}

Hub du sport — relié au [[00 - Dashboard]] et à la [[Stratégie Analyste Contextuel]].

## Ligues

```dataview
LIST FROM "{HUBS_DIR}" WHERE type = "ligue" AND sport = "{bet.sport}"
```

## Paris

```dataview
TABLE WITHOUT ID file.link AS "Pari", profil AS "Profil", ligue AS "Ligue", date AS "Date", cote_betclic AS "Cote", score_confiance AS "Score", statut AS "Statut", profit AS "Profit €"
FROM "{BETS_DIR}"
WHERE sport = "{bet.sport}"
SORT date DESC
```
"""), encoding="utf-8")
        league_note = hubs / f"{safe_filename(bet.ligue)}.md"
        if not league_note.exists() and league_note != sport_note:
            league_note.write_text(render_note(
                {"type": "ligue", "sport": bet.sport, "tags": ["hub/ligue"]},
                f"""# {bet.ligue}

Compétition de [[{bet.sport}]].

```dataview
TABLE WITHOUT ID file.link AS "Pari", profil AS "Profil", date AS "Date", cote_betclic AS "Cote", score_confiance AS "Score", statut AS "Statut", profit AS "Profit €"
FROM "{BETS_DIR}"
WHERE ligue = "{bet.ligue}"
SORT date DESC
```
"""), encoding="utf-8")

    def ensure_monthly_report(self, now: datetime) -> Optional[Path]:
        """Crée la note « Bilan AAAA-MM » du mois courant à partir du modèle."""
        month = now.astimezone(self.tz).strftime("%Y-%m")
        path = self.root / BILAN_DIR / f"Bilan {month}.md"
        template = self.root / "99 - Modèles" / "Modèle - Bilan mensuel.md"
        if path.exists() or not template.exists():
            return None
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(template.read_text(encoding="utf-8").replace("{{mois}}", month), encoding="utf-8")
        return path

    # --- combiné -----------------------------------------------------------------------
    def write_combo(self, bet: dict, bankroll: float, now: datetime) -> Path:
        """Fiche d'un Combiné du jour (ou pari Fun) engagé au grand livre."""
        self.bets_dir.mkdir(parents=True, exist_ok=True)
        local = now.astimezone(self.tz)
        path = self.bets_dir / f"{local:%Y-%m-%d} - Combiné du jour.md"
        legs = bet["legs"]
        meta = {
            "sport": "Combiné", "ligue": bet["competition"], "match": bet["match"],
            "date": _fmt(datetime.fromisoformat(bet["kickoff"].replace("Z", "+00:00")), self.tz),
            "marche": f"Combiné ({len(legs)} sélections)", "selection": bet["selection"],
            "profil": bet["profile"], "score_confiance": bet["score"], "cote_betclic": bet["odd"],
            "fair_odd_pinnacle": round(1 / bet["fair_prob"], 3), "probabilite_reelle": round(bet["fair_prob"] * 100, 2),
            "ev_percent": round(bet["ev"] * 100, 2), "mise_recommandee": bet["stake"],
            "statut": rules.STATUT_EN_ATTENTE, "profit": 0,
            "type": "pari", "id": bet["id"], "type_marche": "combo", "gain_potentiel": bet["potential_payout"],
            "bankroll_reference": bankroll, "detecte_le": _fmt(now, self.tz),
            "liens": sorted({f"[[{l['sport']}]]" for l in legs} | {f"[[{l['competition']}]]" for l in legs}),
            "tags": ["pari", "combine", "profil/combine"],
        }
        rows = "\n".join(f"| {l['match']} | {l['competition']} | {l['selection']} | {l['odd']:.2f}"
                          f"{' (min.)' if l['estimated'] else ''} | {l.get('headline', '')} |" for l in legs)
        body = f"""# 🧩 Combiné du jour — {local:%d/%m/%Y}

> [!info] Engagé par le Fonds Claude le {local:%d/%m/%Y à %H:%M}
> **Cote totale** : **{bet['odd']:.2f}** · **Mise** : **{bet['stake']:.2f} €** · **Gain potentiel** : {bet['potential_payout']:.2f} €
> **Méthode** : [[{STRATEGY_NOTE}]] · [[Profils de risque]] · [[Modèle de Poisson]]

## Sélections

| Match | Compétition | Pari | Cote | Stat clé |
|---|---|---|---|---|
{rows}

Probabilité combinée selon Pinnacle : **{bet['fair_prob'] * 100:.1f} %** (cote juste {1 / bet['fair_prob']:.2f}) ·
EV {bet['ev'] * 100:+.1f} % : les marges de chaque sélection se multiplient dans un combiné.

## Résultat

En attente : réglé automatiquement par `auto_settle` (scores ESPN).

## Notes personnelles

"""
        path.write_text(render_note(meta, body), encoding="utf-8")
        self._bet_index()[bet["id"]] = path
        return path

    # --- règlement ---------------------------------------------------------------------
    def apply_settlement(self, bet: dict, now: datetime) -> Optional[Path]:
        """Reporte dans la fiche le règlement automatique d'un pari (statut, profit, score final)."""
        path = self._bet_index().get(bet["id"])
        if not path or not path.exists():
            return None
        meta, body = split_frontmatter(path.read_text(encoding="utf-8"))
        meta.update(statut=bet["status"], profit=bet["profit"], score_final=bet["final_score"],
                    regle_le=_fmt(now, self.tz))
        if bet.get("settled_odd") and abs(bet["settled_odd"] - bet["odd"]) > 1e-6:
            meta["cote_reglee"] = bet["settled_odd"]
        verdict = {"GAGNE": "✅ Gagné", "PERDU": "❌ Perdu", "REMBOURSE": "↩️ Remboursé"}.get(bet["status"], bet["status"])
        line = (f"\n> [!success] Réglé automatiquement le {now.astimezone(self.tz):%d/%m/%Y à %H:%M}\n"
                f"> {verdict} · score final {bet['final_score']} · profit **{bet['profit']:+.2f} €**\n")
        if "## Suivi" in body:
            body = body.replace("## Suivi", line.strip("\n") + "\n\n## Suivi", 1)
        elif "## Résultat" in body:
            body = body.replace("En attente : réglé automatiquement par `auto_settle` (scores ESPN).", line.strip("\n"), 1)
        else:
            body = body.rstrip("\n") + "\n" + line
        path.write_text(render_note(meta, body), encoding="utf-8")
        return path
