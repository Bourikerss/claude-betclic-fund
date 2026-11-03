"""Point d'entrée CLI : `python bot.py [daily|scan|settle|build-web|quota|sports|test-telegram]`.

`daily` (lancé par launchd à 11 h 30) enchaîne : auto_settle → scan → build_web → git_sync → notify.
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from typing import List, Optional
from zoneinfo import ZoneInfo

from . import build_web, git_sync, rules
from . import sports as sports_mod
from .auto_settle import AutoSettler, SettleReport
from .config import BOT_ROOT, Settings
from .fund import DailyPlan, commit_plan, plan_day
from .ledger import Ledger
from .notifier import TelegramNotifier, format_daily
from .obsidian import ObsidianVault
from .odds_api import OddsApiClient, OddsApiError
from .quota import QuotaManager
from .scanner import ScanReport, Scanner
from .stats_client import StatsClient

log = logging.getLogger("betclic_bot")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="betclic-bot", description="Fonds Claude : paper trading Betclic, capital 10 €")
    parser.add_argument("-v", "--verbose", action="store_true", help="logs détaillés")
    sub = parser.add_subparsers(dest="command")

    daily = sub.add_parser("daily", help="cycle quotidien complet (règlement, paris, site, GitHub, Telegram)")
    daily.add_argument("--no-push", action="store_true", help="ne pas publier sur GitHub")
    daily.add_argument("--no-telegram", action="store_true", help="ne pas envoyer le message Telegram")

    scan = sub.add_parser("scan", help="analyser et engager les paris du jour (consomme des crédits)")
    scan.add_argument("--dry-run", action="store_true", help="aperçu des paris du jour, rien n'est engagé")
    scan.add_argument("--sports", help="clés de sports séparées par des virgules (ex: soccer_epl,soccer_uefa_champs_league)")
    scan.add_argument("--max-sports", type=int, help="plafond de compétitions pour ce run")

    sub.add_parser("settle", help="régler les paris terminés d'après les scores ESPN")
    sub.add_parser("build-web", help="régénérer le site docs/")
    sub.add_parser("quota", help="afficher l'état du quota (aucun crédit consommé)")
    sub.add_parser("sports", help="lister les compétitions éligibles (gratuit)")
    sub.add_parser("notify", help="(r)envoyer le message Telegram du jour")
    sub.add_parser("test-telegram", help="envoyer un message de test")
    return parser


class App:
    def __init__(self, settings: Settings, now: datetime):
        self.settings = settings
        self.now = now
        self.tz = settings.timezone
        self.vault = ObsidianVault(settings.vault_path, settings.timezone)
        self.ledger = Ledger(settings.ledger_path, rules.INITIAL_BANKROLL, now)
        self.stats = StatsClient(settings.stats_cache_path)
        self.quota = QuotaManager(settings.state_path, settings.monthly_credits, settings.credit_reserve,
                                  rules.DAILY_RUNS_PER_DAY, settings.max_sports_per_run)
        self.notifier = TelegramNotifier(settings.telegram_token, settings.telegram_chat_id)
        self.repo = git_sync.repo_root(BOT_ROOT)

    @property
    def site_url(self) -> str:
        return self.settings.site_url or (git_sync.site_url(self.repo) if self.repo else "")

    # --- étapes ------------------------------------------------------------------------
    def settle(self) -> SettleReport:
        report = AutoSettler(self.stats).run(self.ledger, self.now)
        for bet in report.settled:
            self.vault.apply_settlement(bet, self.now)
        self.ledger.save()
        return report

    def scan(self, only: Optional[List[str]] = None, max_sports: Optional[int] = None,
             dry_run: bool = False) -> tuple:
        client = OddsApiClient(self.settings.odds_api_key)
        report = Scanner(self.settings, client, self.quota, self.stats).run(
            now=self.now, only_sports=only, max_sports=max_sports, bankroll=self.ledger.balance,
            lookahead_hours=rules.DAILY_LOOKAHEAD_HOURS)
        plan = plan_day(report.candidates, report.combo_legs, self.ledger, self.now, self.tz)
        if not dry_run:
            commit_plan(plan, self.ledger, self.vault, self.now)
            self.vault.ensure_monthly_report(self.now)
        return report, plan

    def build_web(self) -> None:
        build_web.build(self.ledger, (self.repo or BOT_ROOT.parent) / "docs", self.now, self.tz, self.site_url)

    def publish(self):
        if not self.repo:
            return git_sync.SyncResult(False, "Pas de dépôt git")
        day = self.now.astimezone(ZoneInfo(self.tz)).strftime("%d/%m/%Y")
        return git_sync.sync(self.repo, f"update: bilan et paris du {day}", BOT_ROOT / ".env")

    def notify(self, settled: SettleReport) -> bool:
        """Message du jour : paris engagés aujourd'hui (lus au grand livre) et paris réglés pendant ce run."""
        zone = ZoneInfo(self.tz)
        today = self.now.astimezone(zone).strftime("%Y-%m-%d")
        placed = sorted((b for b in self.ledger.bets.values()
                         if datetime.fromisoformat(b["placed_at"].replace("Z", "+00:00")).astimezone(zone)
                         .strftime("%Y-%m-%d") == today), key=lambda b: (-b["score"], b["placed_at"]))
        singles = [b for b in placed if b["kind"] == "SIMPLE"]
        combo = next((b for b in placed if b["kind"] in ("COMBINE", "FUN")), None)
        text = format_daily(self.ledger.metrics(), settled.settled, singles, combo, self.site_url, self.tz)
        return self.notifier.send(text)


def _print_scan(report: ScanReport, plan: DailyPlan, dry_run: bool) -> None:
    print(f"Compétitions scannées : {', '.join(report.sports_scanned) or 'aucune'}")
    print(f"Matchs : {report.events} · issues éligibles : {len(report.candidates)} · "
          f"sélections de combiné : {len(report.combo_legs)}")
    print(f"Crédits utilisés : {report.credits_used} · restants : {report.credits_remaining}")
    if report.stop_reason:
        print(f"Arrêt : {report.stop_reason}")
    verb = "Proposés" if dry_run else "Engagés"
    print(f"\n{verb} (solde {plan.base_balance:.2f} €, plafond du jour {plan.budget:.2f} €) :")
    for pos in plan.positions:
        r = pos.record
        print(f"  {r['profile']:<10} {r['score']:3d}/100  {r['match']} · {r['selection']} @ {r['odd']:.2f} — {r['stake']:.2f} €")
    for line in plan.skipped:
        print(f"  écarté : {line}")
    if plan.combo is None and report.combo_legs:
        print("  Pas de combiné : sélections éligibles (cote totale visée 1.70 – 2.40, matchs différents) :")
        for leg in report.combo_legs[:6]:
            o = leg.outcome
            print(f"    {o.home_team} vs {o.away_team} · {o.selection} @ {leg.odd:.2f} (convergence {leg.convergence:.2f})")
    if report.sports_scanned:
        _print_diagnostic(report.stats)


def _counter_line(counter) -> str:
    return " · ".join(f"{k} : {v}" for k, v in counter.most_common()) or "aucun"


def _print_diagnostic(stats) -> None:
    print("\n— Diagnostic —")
    print(f"Matchs avec Pinnacle + Betclic : {stats.events_with_both}/{stats.events}")
    print("Lignes comparées : " + (" · ".join(f"{m} {n}" for m, n in sorted(stats.compared.items())) or "aucune"))
    print("Non comparables : " + _counter_line(stats.skipped))
    if stats.derived:
        print(f"Issues dérivées (modèle de Poisson) : {stats.derived}")
    print("Issues éligibles par profil : " + (" · ".join(f"{p} {stats.candidates.get(p, 0)}" for p in rules.PROFILES)))
    print("Issues écartées : " + _counter_line(stats.rejections))
    if stats.near_misses:
        print("Issues les plus proches du seuil d'EV, par profil :")
        for profile in rules.PROFILES:
            for ev, _, label in sorted((m for m in stats.near_misses if m[1] == profile), reverse=True)[:2]:
                print(f"  {profile:<10} {ev * 100:+6.2f} %  {label}")
    if stats.teams_looked_up:
        print(f"Équipes trouvées chez ESPN : {stats.teams_with_stats}/{stats.teams_looked_up}")


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(name)s — %(message)s")
    settings = Settings.from_env()
    now = datetime.now(timezone.utc)
    app = App(settings, now)
    command = args.command or "daily"

    if command == "quota":
        for key, value in app.quota.summary(now).items():
            print(f"{key:>22} : {value}")
        return 0
    if command == "test-telegram":
        ok = app.notifier.send("✅ <b>Fonds Claude</b> — connexion Telegram OK")
        print("Message envoyé" if ok else "Échec : vérifier TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID")
        return 0 if ok else 1
    if command == "notify":
        ok = app.notify(SettleReport())
        print("Message envoyé" if ok else "Échec de l'envoi Telegram")
        return 0 if ok else 1
    if command == "settle":
        rep = app.settle()
        for b in rep.settled:
            print(f"{b['status']:<10} {b['profit']:+6.2f} €  {b['label']}  ({b['final_score']})")
        print(f"{len(rep.settled)} pari(s) réglé(s), {rep.still_open} en cours — solde {app.ledger.balance:.2f} €")
        return 0
    if command == "build-web":
        app.build_web()
        print(f"Site régénéré : {(app.repo or BOT_ROOT.parent) / 'docs'}")
        return 0
    if command == "sports":
        all_sports, _ = OddsApiClient(settings.odds_api_key).get_sports()
        eligible = sports_mod.eligible_sports(all_sports)
        print("Poids  Couvert. Clé                                      Compétition")
        for key, sport in sorted(eligible.items(), key=lambda kv: -sports_mod.sport_weight(kv[1])):
            cov = app.quota.coverage(key)
            cov_txt = "   ?" if cov is None else f"{cov * 100:3.0f} %"
            print(f"{sports_mod.sport_weight(sport):5.1f}  {cov_txt:>7}  {key:<40} {sport['title']}")
        return 0

    if command == "scan":
        only = [s.strip() for s in args.sports.split(",")] if args.sports else None
        try:
            report, plan = app.scan(only, args.max_sports, args.dry_run)
        except (OddsApiError, ValueError) as exc:
            logging.error("Scan interrompu : %s", exc)
            return 1
        _print_scan(report, plan, args.dry_run)
        return 0

    # --- daily : chaque étape est isolée, une panne n'empêche pas les suivantes -----------------
    settled, plan, failures = SettleReport(), None, []
    try:
        settled = app.settle()
        log.info("Règlement : %d pari(s) réglé(s), %d en cours", len(settled.settled), settled.still_open)
    except Exception as exc:  # noqa: BLE001
        failures.append(f"règlement : {exc}"); log.exception("auto_settle")
    try:
        report, plan = app.scan()
        _print_scan(report, plan, dry_run=False)
    except Exception as exc:  # noqa: BLE001
        failures.append(f"scan : {exc}"); log.exception("scan")
    try:
        app.build_web()
    except Exception as exc:  # noqa: BLE001
        failures.append(f"site : {exc}"); log.exception("build_web")
    if not getattr(args, "no_push", False):
        result = app.publish()
        log.info("GitHub : %s", result.detail)
        if not result.ok:
            failures.append(f"GitHub : {result.detail}")
    if not getattr(args, "no_telegram", False):
        app.notify(settled)
    for f in failures:
        log.error("Étape en échec — %s", f)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
