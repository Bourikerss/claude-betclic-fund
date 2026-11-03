"""Analyse d'un scan : sports → cotes → stats ESPN → marchés dérivés → candidats et sélections de combiné.

L'engagement des paris (grand livre, fiches) est fait par `fund.py` ; les notifications par le pipeline quotidien.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Sequence, Tuple

from . import rules
from . import sports as sports_mod
from .config import Settings
from .analyzer import analyze, select_top, stats_convergence
from .combo import ComboLeg, is_leg_candidate
from .derived import derive_outcomes
from .detector import DetectionStats, compare_event
from .models import Opportunity
from .odds_api import OddsApiClient, OddsApiError, QuotaExhausted
from .quota import QuotaManager
from .stats_client import StatsClient

log = logging.getLogger(__name__)


@dataclass
class ScanReport:
    budget: int = 0
    bankroll: float = 0.0
    sports_scanned: List[str] = field(default_factory=list)
    events: int = 0
    candidates: List[Opportunity] = field(default_factory=list)  # toutes les issues éligibles
    bets: List[Opportunity] = field(default_factory=list)        # Top du scan (aperçu, avant le grand livre)
    combo_legs: List[ComboLeg] = field(default_factory=list)     # sélections éligibles au Combiné du jour
    credits_used: int = 0
    credits_remaining: Optional[int] = None
    stop_reason: Optional[str] = None
    stats: DetectionStats = field(default_factory=DetectionStats)
    coverage: Dict[str, Tuple[int, int]] = field(default_factory=dict)  # sport → (comparables, total)


class Scanner:
    def __init__(self, settings: Settings, client: OddsApiClient, quota: QuotaManager,
                 stats_client: Optional[StatsClient] = None):
        self.settings = settings
        self.stats_client = stats_client
        self.client = client
        self.quota = quota

    def run(self, now: Optional[datetime] = None, only_sports: Optional[Sequence[str]] = None,
            max_sports: Optional[int] = None, bankroll: Optional[float] = None,
            lookahead_hours: Optional[int] = None) -> ScanReport:
        now = now or datetime.now(timezone.utc)
        report = ScanReport()
        report.budget = self.quota.sports_budget(now)
        if max_sports is not None:
            report.budget = min(report.budget, max_sports)
        if report.budget <= 0:
            report.stop_reason = "Budget de crédits insuffisant pour ce run"
            report.credits_remaining = self.quota.remaining(now)
            return report

        report.bankroll = bankroll if bankroll is not None else rules.INITIAL_BANKROLL

        all_sports, info = self.client.get_sports()
        self.quota.update_from_api(info, now)
        eligible = sports_mod.eligible_sports(all_sports)
        if only_sports:
            eligible = {k: v for k, v in eligible.items() if k in set(only_sports)}
        ranking = self.quota.rank({k: sports_mod.sport_weight(v) for k, v in eligible.items()}, now)

        start, end = now, now + timedelta(hours=lookahead_hours or self.settings.lookahead_hours)
        max_checks = report.budget * 4
        try:
            for checks, key in enumerate(ranking):
                if len(report.sports_scanned) >= report.budget or checks >= max_checks:
                    break
                sport = eligible[key]
                try:
                    upcoming, info = self.client.get_events(key, start, end)  # gratuit
                    self.quota.update_from_api(info, now)
                except OddsApiError as exc:
                    log.warning("Events %s indisponibles : %s", key, exc)
                    continue
                if not upcoming:
                    self.quota.mark_scanned(key, now)
                    continue

                try:
                    events, info = self.client.get_odds(key, start, end)
                except QuotaExhausted as exc:
                    report.stop_reason = str(exc)
                    break
                except OddsApiError as exc:
                    log.warning("Cotes %s indisponibles : %s", key, exc)
                    continue
                report.credits_used += self.quota.record_call(key, info, now)
                report.sports_scanned.append(key)
                report.events += len(events)
                # Match comparable = Pinnacle ET Betclic présents (la NHL a Betclic mais pas Pinnacle).
                comparable = sum(
                    1 for e in events
                    if set(rules.BOOKMAKERS) <= {b.get("key") for b in e.get("bookmakers", [])}
                )
                self.quota.record_coverage(key, len(events), comparable)
                report.coverage[key] = (comparable, len(events))
                self._analyze_events(events, sport, report, now)
        finally:
            self.quota.save()

        report.bets = select_top(report.candidates)
        report.credits_remaining = self.quota.remaining(now)
        return report

    def _team_stats(self, sport_key: str, home: str, away: str, stats: DetectionStats):
        if not self.stats_client or not self.stats_client.supports(sport_key):
            return None, None
        try:
            found = self.stats_client.match_stats(sport_key, home, away)
        except Exception as exc:  # une panne ESPN ne doit jamais bloquer le scan
            log.warning("Stats ESPN indisponibles pour %s vs %s : %s", home, away, exc)
            found = (None, None)
        stats.teams_looked_up += 2
        stats.teams_with_stats += sum(t is not None for t in found)
        return found

    def _analyze_events(self, events: List[dict], sport: dict, report: ScanReport, now: datetime) -> None:
        sport_name = sports_mod.sport_name(sport["group"])
        for event in events:
            league = sports_mod.league_name(event.get("sport_title") or sport.get("title", ""))
            outcomes = compare_event(event, self.settings.devig_method, now, report.stats)
            if not outcomes:
                continue
            home, away = self._team_stats(event["sport_key"], event["home_team"], event["away_team"], report.stats)
            if event["sport_key"].startswith("soccer_"):
                real = {(o.market, o.outcome_name, o.point) for o in outcomes}
                derived = [o for o in derive_outcomes(event, outcomes, home, away, self.settings.devig_method)
                           if (o.market, o.outcome_name, o.point) not in real]
                report.stats.derived += len(derived)
                outcomes = outcomes + derived
            for outcome in outcomes:
                opp = analyze(outcome, sport_name, league, report.bankroll, home, away, report.stats)
                if opp:
                    report.candidates.append(opp)
                if home is not None and away is not None:
                    conv = stats_convergence(outcome, home, away)
                    if is_leg_candidate(outcome, conv.score):
                        report.combo_legs.append(ComboLeg(outcome, conv.score, conv.headline, sport_name, league))
