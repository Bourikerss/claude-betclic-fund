---
type: technique
tags: [technique, api]
---

# Gestion du Quota API (500 crédits / mois)

Partie de : [[Architecture du Bot]] · Stratégie : [[Stratégie Analyste Contextuel]]

## Coûts The Odds API v4

| Endpoint | Coût |
|---|---|
| `GET /v4/sports` | **0** |
| `GET /v4/sports/{sport}/events` | **0** |
| `GET /v4/sports/{sport}/odds` football (`h2h,totals` × 1 région) | **2 crédits** |
| `GET /v4/sports/{sport}/odds` tennis (`h2h` × 1 région) | **1 crédit** |

500 crédits ≈ **235 scans de compétition de football par mois** (réserve de 30 déduite) ≈ 8 par jour.

> [!info] Totals en football (03/11/2026)
> Les lignes Plus/Moins de Pinnacle calibrent le [[Modèle de Poisson]] des marchés internes au match.

> [!info] Pourquoi `h2h` seul
> Le 02/11/2026, le diagnostic du scan a montré que The Odds API ne fournit Betclic qu'en 1N2 / vainqueur :
> sur la Ligue des Champions, 11 matchs sur 11 avaient Betclic en `h2h`, mais aucun en `totals` ou `spreads`.
> Les demander coûtait 3 crédits au lieu de 1 pour rien. Sur la NBA, Betclic était totalement absent (0 match sur 15).

## Stratégie d'économie

0. **Compétitions éligibles** : uniquement celles couvertes par les stats ESPN (Premier League, Ligue 1, Liga,
   Serie A, Bundesliga, Ligue des Champions, Ligue Europa, NBA) et les tournois ATP/WTA.
   Aucun crédit sur Championship, Brésil, AHL… (03/11/2026).

1. **Découverte gratuite** des sports actifs (`/sports`).
2. **Pré-vérification gratuite** (`/events`) : on ne paie jamais un scan pour un sport sans match dans les `LOOKAHEAD_HOURS` (48 h par défaut).
3. **Budget par exécution** :
   $$\text{sports} = \text{arrondi}\left(\frac{\text{crédits restants} - \text{réserve}}{\text{jours restants} \times \text{runs/jour} \times 1}\right)$$
   Recalculé à chaque run → les crédits non dépensés sont redistribués automatiquement.
4. **Rotation pondérée** : score = poids × couverture Betclic × heures depuis le dernier scan (plafonnées à 72 h).
5. **Couverture apprise** : à chaque scan, le bot mesure la part des matchs comparables, où [[Pinnacle]] **et** [[Betclic]] sont présents
   (moyenne mobile, 50 % sur la dernière mesure). Un sport sans Betclic tombe à un facteur 0.1 :
   il n'est pas exclu, mais retesté seulement tous les quelques jours. Exemple au 02/11/2026 :
   NBA 0 % (0/15, pas de Betclic) et NHL 0 % (0/15, pas de Pinnacle) → rétrogradées ; Ligue des Champions et ATP Paris 100 %.
   Voir la couverture : `.venv/bin/python bot.py sports` (colonne « Couvert. »).

| Poids | Sports |
|---|---|
| 3.0 | Premier League, Ligue 1, Ligue des Champions, NBA |
| 2.5 | Liga, Serie A, Bundesliga, ATP / WTA |
| 2.0 | Europa League, NHL, NFL, Euroleague, Top 14 |
| 1.5 | Ligue 2, Eredivisie, Primeira Liga |
| 0.5 | Tous les autres sports éligibles |

Poids modifiables dans `betclic-bot/src/betclic_bot/sports.py`.

6. **Source de vérité** : l'en-tête `x-requests-remaining` renvoyé par l'API, plafonné par le budget mensuel local.
7. **Arrêt immédiat** si l'API répond `OUT_OF_USAGE_CREDITS`.

## Planification (launchd, une fois par jour à 11 h 30)

Une seule exécution quotidienne (`DAILY_RUNS_PER_DAY = 1`) → ~8 compétitions par run en début de mois.
Les statistiques et les scores ESPN ne consomment **aucun crédit**.

Agent macOS : `~/Library/LaunchAgents/fr.bot-sporif.betclic-scan.plist`, commande `bot.py daily`.
Si le Mac dormait à 11 h 30, le pipeline part **au réveil**. Mac éteint : le créneau est perdu.

```bash
launchctl print gui/$(id -u)/fr.bot-sporif.betclic-scan            # état, dernier code de sortie
launchctl kickstart gui/$(id -u)/fr.bot-sporif.betclic-scan        # lancer le cycle quotidien maintenant
launchctl bootout gui/$(id -u)/fr.bot-sporif.betclic-scan          # désactiver
tail -n 50 betclic-bot/data/bot.log                                 # journal
```

> [!tip] Montée en charge
> Le plan payant « 20K » (20 000 crédits) permet de scanner tous les sports plusieurs fois par jour :
> il suffit d'ajuster `MONTHLY_CREDITS`, `RUNS_PER_DAY` et `MAX_SPORTS_PER_RUN` dans `.env`.

Vérifier l'état : `.venv/bin/python bot.py quota`
