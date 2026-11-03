from betclic_bot.ledger import Metrics
from betclic_bot.notifier import format_daily


def _metrics(equity=10.42, profit=0.42):
    return Metrics(initial=10.0, balance=8.0, equity=equity, exposure=2.42, profit=profit, roi=profit / 10,
                   yield_=0.1, winrate=0.5, won=1, lost=1, void=0, pending=3, staked_settled=2.0,
                   max_drawdown=0.5, max_drawdown_pct=0.05)


SINGLE = {"kind": "SIMPLE", "profile": "SAFE", "match": "Porto vs Napoli", "competition": "Ligue des Champions",
          "kickoff": "2026-11-04T20:00:00Z", "selection": "Porto", "odd": 1.85, "stake": 1.0,
          "headline": "Porto : **6V-0N-1D** à domicile"}
FUN = dict(SINGLE, kind="FUN", profile="AUDACIEUX", selection="Match nul", odd=3.45, stake=0.5)
COMBO = {"kind": "COMBINE", "profile": "COMBINE", "odd": 2.05, "stake": 0.5, "legs": [
    {"match": "PSG vs Lens", "selection": "PSG", "odd": 1.40},
    {"match": "Inter vs Roma", "selection": "Plus de 1.5 buts", "odd": 1.46}]}


def test_daily_message_exact_format():
    settled = [{"status": "GAGNE", "profit": 0.85}, {"status": "PERDU", "profit": -0.70}]
    msg = format_daily(_metrics(), settled, [SINGLE], COMBO, "https://maxance.github.io/claude-betclic-fund/")
    assert msg.split("\n") == [
        "💰 <b>PORTEFEUILLE CLAUDE : 10,42 €</b> (+0,42 € | ROI : +4,2 %)",
        "📅 <i>Hier : 1G - 1P (+0,15 €)</i>",
        "",
        "🎯 <b>LES PARIS DU JOUR</b>",
        "",
        "🛡️ <b>Porto vs Napoli</b> (Ligue des Champions · mer. 21h00)",
        "👉 <b>Porto</b> @ <b>1,85</b> — Mise : <b>1,00 €</b>",
        "📊 <i>Porto : 6V-0N-1D à domicile</i>",
        "",
        "🧩 <b>COMBINÉ DU JOUR</b> @ <b>2,05</b> — Mise : <b>0,50 €</b>",
        "• PSG vs Lens : <b>PSG</b> (@ 1,40)",
        "• Inter vs Roma : <b>Plus de 1.5 buts</b> (@ 1,46)",
        "",
        "🌐 <b>Suivi en direct :</b> https://maxance.github.io/claude-betclic-fund/",
    ]


def test_negative_day_and_fun_bet():
    msg = format_daily(_metrics(9.3, -0.7), [{"status": "PERDU", "profit": -0.7}], [], FUN, "https://x/")
    assert "(−0,70 € | ROI : −7,0 %)" in msg
    assert "Hier : 0G - 1P (−0,70 €)" in msg
    assert "🎲 <b>PARI FUN DU JOUR</b>\n🎲 <b>Porto vs Napoli</b>" in msg


def test_no_bets_today():
    msg = format_daily(_metrics(10.0, 0.0), [], [], None, "https://x/")
    assert "Aucun pari aujourd'hui" in msg and "Hier : 0G - 0P (+0,00 €)" in msg


def test_html_is_escaped():
    msg = format_daily(_metrics(), [], [dict(SINGLE, match="A&B <FC> vs C")], None, "https://x/")
    assert "A&amp;B &lt;FC&gt; vs C" in msg
