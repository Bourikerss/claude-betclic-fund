# betclic-bot — Fonds Claude (Challenge 10 €)

Paper trading autonome : Claude gère un capital fictif de 10 € sur Betclic. Cotes Pinnacle (référence) + Betclic
+ statistiques ESPN, 2 à 4 paris simples et 1 Combiné du jour, règlement automatique, site public GitHub Pages.
Règles métier : [CLAUDE.md](../CLAUDE.md) · Documentation : `01 - Architecture & Stratégie/` dans le coffre.

## Installation

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env    # renseigner ODDS_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
```

## Commandes

| Commande | Effet | Crédits |
|---|---|---|
| `.venv/bin/python bot.py daily` | Cycle quotidien : règlement, paris du jour, site, GitHub, Telegram | ~8–16 |
| `.venv/bin/python bot.py scan` | Analyse + engagement des paris du jour au grand livre | 2 / compétition |
| `.venv/bin/python bot.py scan --dry-run --max-sports 1` | Scan sans écrire ni notifier + diagnostic | 1 |
| `.venv/bin/python bot.py scan --sports soccer_epl,basketball_nba` | Scanner des sports précis | 1 / sport |
| `.venv/bin/python bot.py sports` | Sports éligibles et poids | 0 |
| `.venv/bin/python bot.py quota` | Budget restant | 0 |
| `.venv/bin/python bot.py settle` | Règle les paris terminés (scores ESPN) | 0 |
| `.venv/bin/python bot.py build-web` | Régénère le site `docs/` | 0 |
| `.venv/bin/python bot.py test-telegram` | Message de test | 0 |
| `.venv/bin/python -m pytest` | Tests | 0 |

## Planification (launchd, chaque jour à 11 h 30 : `bot.py daily`)

Agent `~/Library/LaunchAgents/fr.bot-sporif.betclic-scan.plist` (copie dans `deploy/`). Il rattrape un
scan manqué pendant la veille du Mac. Journal : `data/bot.log`.

```bash
launchctl kickstart gui/$(id -u)/fr.bot-sporif.betclic-scan   # lancer un scan maintenant
launchctl bootout gui/$(id -u)/fr.bot-sporif.betclic-scan     # désactiver
```

## Structure

```
src/betclic_bot/
  rules.py      règles métier (miroir de CLAUDE.md)
  odds_api.py   client The Odds API v4
  quota.py      budget 500 crédits/mois + rotation des sports
  sports.py     sports éligibles, noms FR, priorités
  devig.py      retrait de marge Pinnacle
  value.py      EV, mise selon le profil
  detector.py   appariement Pinnacle ↔ Betclic, issue par issue
  stats_client.py  stats ESPN gratuites (classement, forme, blessures NBA), cache 24 h
  poisson.py    modèle de Poisson calibré sur Pinnacle (1N2 + totals)
  derived.py    marchés dérivés : double chance, DNB, BTTS, Over/Under, buts d'une équipe, handicap
  analyzer.py   Score d'Opportunité /100, 3 profils, argumentaire, Top du scan (variété des marchés)
  obsidian.py   fiches d'analyse Markdown, hubs, bilan mensuel, settle
  notifier.py   message Telegram quotidien
  ledger.py     grand livre data/ledger.json (paper trading, 10 €)
  fund.py       paris du jour, mises proportionnelles, plafond 35 %
  combo.py      Combiné du jour
  auto_settle.py règlement automatique (scores ESPN)
  build_web.py  site docs/ (GitHub Pages) — sources dans web/
  git_sync.py   commit + push quotidien, garde-fous anti-secrets
  scanner.py    orchestration
tests/          pytest (aucun appel réseau)
```
