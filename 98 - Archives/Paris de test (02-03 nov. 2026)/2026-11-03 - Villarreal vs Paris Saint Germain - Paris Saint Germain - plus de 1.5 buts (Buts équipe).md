---
sport: Football
ligue: Ligue des Champions
match: Villarreal vs Paris Saint Germain
date: 2026-11-03T21:00
marche: Buts d'une équipe
selection: 'Paris Saint Germain : plus de 1.5 buts'
profil: SAFE
score_confiance: 48
cote_betclic: 1.4
fair_odd_pinnacle: 1.521
probabilite_reelle: 65.74
ev_percent: -7.96
mise_recommandee: 1.0
statut: EN_ATTENTE
profit: 0
type: pari
id: a341241606cb5b1b59e425d00be64883_team_totals_paris-saint-germain-over_+1.5
type_marche: team_totals
cote_source: estimee
cote_estimee: 1.4
mise_percent: 2.0
mise_theorique: 0.29
score_marche: 18.0
score_cote: 0.1
score_stats: 30.0
convergence_stats: 1.0
cote_pinnacle: 1.52
marge_pinnacle_percent: 3.24
marge_betclic_percent: 9.01
bankroll_reference: 14.63
cote_betclic_actuelle: 1.4
ev_actuel_percent: -7.96
detecte_le: 2026-11-03T20:13
derniere_maj: 2026-11-03T20:13
sport_key: soccer_uefa_champs_league
event_id: a341241606cb5b1b59e425d00be64883
liens: ['[[Football]]', '[[Ligue des Champions]]']
tags: [pari, football, profil/safe]
---

# 🛡️ SAFE — Villarreal vs Paris Saint Germain : Paris Saint Germain : plus de 1.5 buts

> [!info] Analyse générée le 03/11/2026 à 20:13
> **Profil** : Safe (Base solide) · **Score d'Opportunité** : **48/100**
> **Sport** : [[Football]] · **Ligue** : [[Ligue des Champions]] · **Méthode** : [[Stratégie Analyste Contextuel]] · [[Profils de risque]]
> **Coup d'envoi** : 03/11/2026 21:00

## 🎯 Le pari

| Indicateur | Valeur |
|---|---|
| Marché | Buts d'une équipe |
| Sélection | **Paris Saint Germain : plus de 1.5 buts** |
| Cote minimale à exiger sur Betclic | **1.4** |
| Cote Betclic estimée | ≈ 1.4 (non publiée via l'API) |
| Source de la probabilité | modèle de Poisson calé sur Pinnacle |
| Cote juste Pinnacle (sans marge) | 1.521 |
| Probabilité réelle | 65.74 % |
| Expected Value (estimée) | -7.96 % |
| Marge Betclic (1N2 du match) | 9.01 % |

**[[Score d'Opportunité]] : 48/100** = marché 18/35 + cote 0.1/35 + stats 30/30 (convergence 100 %)

## 📊 Contexte sportif

| | Villarreal | Paris Saint Germain |
|---|---|---|
| Classement | 9/20 · Liga | 1/18 · Ligue 1 |
| Phase de ligue UEFA | 19/36 | 1/36 |
| Bilan saison | 3V-3N-5D | 6V-2N-1D |
| Forme (5 derniers, dernier à droite) | `VNDVD` | `VVVVV` |
| Série en cours | 1 défaite | 9 victoires |
| Domicile (dom.) / Extérieur (ext.) | dom. 2V-1N-3D | ext. 5V-2N-0D |
| Buts marqués / match | 1.64 | 2.92 |
| Buts encaissés / match | 1.64 | 1.25 |
| Différence / match | 0.00 | 1.67 |
| Absents / incertains | — | — |

**Derniers matchs — Villarreal**
- 30/10 · Espanyol (dom.) 0-1 **D**
- 24/10 · Valencia (ext.) 2-1 **V**
- 20/10 · Liverpool (ext.) 3-4 **D**
- 17/10 · Elche (dom.) 0-0 **N**
- 13/10 · Napoli (dom.) 3-1 **V**

**Derniers matchs — Paris Saint-Germain**
- 30/10 · Le Havre AC (ext.) 5-1 **V**
- 26/10 · Lyon (dom.) 2-0 **V**
- 20/10 · Barcelona (dom.) 4-2 **V**
- 17/10 · Strasbourg (ext.) 3-1 **V**
- 14/10 · Manchester City (ext.) 4-2 **V**

*Source : ESPN (classement et calendrier, cache 24 h).*

## 🧠 Argumentaire du pronostic

- Probabilité réelle **65.7 %** (cote juste 1.52), calculée sur les cotes Pinnacle (modèle de Poisson pour les marchés de buts).
- Cote Betclic non publiée via l'API : **exiger au moins 1.40** sur Betclic (estimation ≈ 1.40 avec sa marge 1N2 de 9.0 % sur ce match).
- Buts attendus pour Paris Saint Germain : 2.4 (ligne 1.5)
- Paris Saint-Germain : 2.9 buts marqués / 1.2 encaissés par match

## ⚠️ Point de vigilance

> [!warning] Marge bookmaker : cote 8.0 % sous la cote juste, espérance négative selon Pinnacle (≈ 8 cts perdus par euro misé en moyenne)

## 💰 Gestion de mise

- Mise conseillée : **1.00 €** (plancher de 1.00 €).
- À titre indicatif : profil **Safe (Base solide)** → 2 % de la bankroll = 0.29 € théoriques.
- Mise à plat par profil (pas de Kelly : l'EV est souvent proche de zéro ou négative).
- Ne jamais dépasser la mise conseillée pour « se refaire » ; voir [[Bankroll]].

## Historique des cotes
- 03/11 20:13 — Betclic ≈ 1.4 (estimée, minimum 1.4) · fair 1.521 · EV -7.96 %

## Suivi

- [ ] Pari placé sur Betclic
- Une fois le match terminé : passer `statut` à `GAGNE`, `PERDU`, `REMBOURSE` ou `NON_JOUE`, puis lancer `python bot.py settle`.
- Si la cote ou la mise réellement jouée diffère : ajouter `cote_prise` / `mise_reelle` dans les propriétés.

## Notes personnelles

