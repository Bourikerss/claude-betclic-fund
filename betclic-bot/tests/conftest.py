from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from betclic_bot.stats_client import GameResult, TeamStats

NOW = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)


def _book(key, markets):
    return {"key": key, "title": key, "last_update": "2026-11-02T11:59:00Z",
            "markets": [{"key": k, "last_update": "2026-11-02T11:59:00Z", "outcomes": o} for k, o in markets.items()]}


@pytest.fixture
def now():
    return NOW


@pytest.fixture
def soccer_event():
    """Arsenal vs Chelsea.

    h2h : Arsenal 1.65 (SAFE, p 59.4 %, EV −2.0 %), Nul 3.60 (EV −15.5 % → écarté), Chelsea 5.00 (hors profils).
    totals 2.5 : Over 2.05 (SWEET_SPOT, EV ≈ +2.5 %), Under 1.72 (EV −14 % → écarté).
    spreads : ligne Betclic -1.0 absente chez Pinnacle (-0.5) → ignorée.
    """
    return {
        "id": "evt123",
        "sport_key": "soccer_epl",
        "sport_title": "EPL",
        "commence_time": "2026-11-03T20:00:00Z",
        "home_team": "Arsenal",
        "away_team": "Chelsea",
        "bookmakers": [
            _book("pinnacle", {
                "h2h": [{"name": "Arsenal", "price": 1.62}, {"name": "Chelsea", "price": 5.60},
                        {"name": "Draw", "price": 4.10}],
                "totals": [{"name": "Over", "price": 1.95, "point": 2.5},
                           {"name": "Under", "price": 1.95, "point": 2.5}],
                "spreads": [{"name": "Arsenal", "price": 1.90, "point": -0.5},
                            {"name": "Chelsea", "price": 2.00, "point": 0.5}],
            }),
            _book("betclic_fr", {
                "h2h": [{"name": "Arsenal", "price": 1.65}, {"name": "Chelsea", "price": 5.00},
                        {"name": "Draw", "price": 3.60}],
                "totals": [{"name": "Over", "price": 2.05, "point": 2.5},
                           {"name": "Under", "price": 1.72, "point": 2.5}],
                "spreads": [{"name": "Arsenal", "price": 2.20, "point": -1.0},
                            {"name": "Chelsea", "price": 1.65, "point": 1.0}],
            }),
        ],
    }


def make_team(name, results, *, home_flags=None, rank=1, size=20, scored=None, conceded=None,
              sport="soccer", injuries=(), last_date=NOW - timedelta(days=3)):
    """Équipe fictive. `results` : liste (marqués, encaissés), du plus récent au plus ancien."""
    home_flags = home_flags or [i % 2 == 0 for i in range(len(results))]
    games = [GameResult(date=last_date - timedelta(days=7 * i), home=home_flags[i], opponent=f"Adv {i}",
                        scored=s, conceded=c, competition="eng.1")
             for i, (s, c) in enumerate(results)]
    wins = sum(s > c for s, c in results)
    draws = sum(s == c for s, c in results)
    return TeamStats(name=name, team_id=name.lower(), sport=sport, competition="eng.1", rank=rank,
                     table_size=size, played=len(results), wins=wins, draws=draws,
                     losses=len(results) - wins - draws,
                     scored=scored if scored is not None else sum(s for s, _ in results),
                     conceded=conceded if conceded is not None else sum(c for _, c in results),
                     games=games, injuries=list(injuries))


@pytest.fixture
def strong_home():
    """Arsenal : 1er, 5 victoires, solide à domicile, beaucoup de buts."""
    return make_team("Arsenal", [(3, 1), (2, 0), (3, 1), (2, 1), (4, 0), (2, 0)], rank=1)


@pytest.fixture
def weak_away():
    """Chelsea : 15e, en difficulté, perd à l'extérieur."""
    return make_team("Chelsea", [(1, 2), (0, 1), (1, 1), (2, 3), (1, 2), (0, 2)],
                     home_flags=[False, True, False, True, False, True], rank=15)
