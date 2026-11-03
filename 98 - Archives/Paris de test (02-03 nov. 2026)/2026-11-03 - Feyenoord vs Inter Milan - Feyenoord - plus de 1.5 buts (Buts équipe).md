---
sport: Football
ligue: Ligue des Champions
match: Feyenoord vs Inter Milan
date: 2026-11-03T21:00
marche: Buts d'une équipe
selection: 'Feyenoord : plus de 1.5 buts'
profil: SWEET_SPOT
score_confiance: 36
cote_betclic: 1.95
fair_odd_pinnacle: 2.119
probabilite_reelle: 47.18
ev_percent: -7.99
mise_recommandee: 1.0
statut: EN_ATTENTE
profit: 0
type: pari
id: f6f3cf01c2b20b7f746b5a06097a0569_team_totals_feyenoord-over_+1.5
type_marche: team_totals
cote_source: estimee
cote_estimee: 1.95
mise_percent: 1.5
mise_theorique: 0.22
score_marche: 15.7
score_cote: 0.0
score_stats: 20.5
convergence_stats: 0.682
cote_pinnacle: 2.12
marge_pinnacle_percent: 2.72
marge_betclic_percent: 8.96
bankroll_reference: 14.63
cote_betclic_actuelle: 1.95
ev_actuel_percent: -7.99
detecte_le: 2026-11-03T20:13
derniere_maj: 2026-11-03T20:13
sport_key: soccer_uefa_champs_league
event_id: f6f3cf01c2b20b7f746b5a06097a0569
liens: ['[[Football]]', '[[Ligue des Champions]]']
tags: [pari, football, profil/sweet_spot]
---

# 🎯 SWEET SPOT — Feyenoord vs Inter Milan : Feyenoord : plus de 1.5 buts

> [!info] Analyse générée le 03/11/2026 à 20:13
> **Profil** : Sweet Spot (Équilibre cote / sécurité) · **Score d'Opportunité** : **36/100**
> **Sport** : [[Football]] · **Ligue** : [[Ligue des Champions]] · **Méthode** : [[Stratégie Analyste Contextuel]] · [[Profils de risque]]
> **Coup d'envoi** : 03/11/2026 21:00

## 🎯 Le pari

| Indicateur | Valeur |
|---|---|
| Marché | Buts d'une équipe |
| Sélection | **Feyenoord : plus de 1.5 buts** |
| Cote minimale à exiger sur Betclic | **1.95** |
| Cote Betclic estimée | ≈ 1.95 (non publiée via l'API) |
| Source de la probabilité | modèle de Poisson calé sur Pinnacle |
| Cote juste Pinnacle (sans marge) | 2.119 |
| Probabilité réelle | 47.18 % |
| Expected Value (estimée) | -7.99 % |
| Marge Betclic (1N2 du match) | 8.96 % |

**[[Score d'Opportunité]] : 36/100** = marché 15.7/35 + cote 0/35 + stats 20.5/30 (convergence 68 %)

## 📊 Contexte sportif

| | Feyenoord | Inter Milan |
|---|---|---|
| Classement | 1/18 · Eredivisie | 2/20 · Serie A |
| Phase de ligue UEFA | 26/36 | 20/36 |
| Bilan saison | 7V-4N-0D | 8V-1N-1D |
| Forme (5 derniers, dernier à droite) | `VVDNN` | `VVVVD` |
| Série en cours | 2 nuls | 1 défaite |
| Domicile (dom.) / Extérieur (ext.) | dom. 3V-3N-0D | ext. 3V-1N-2D |
| Buts marqués / match | 2.64 | 2.38 |
| Buts encaissés / match | 1.43 | 1.46 |
| Différence / match | 1.21 | 0.92 |
| Absents / incertains | — | — |

**Derniers matchs — Feyenoord Rotterdam**
- 31/10 · Fortuna Sittard (dom.) 1-1 **N**
- 25/10 · PSV Eindhoven (ext.) 1-1 **N**
- 21/10 · Real Betis (ext.) 0-1 **D**
- 17/10 · Telstar (ext.) 4-3 **V**
- 14/10 · Como (dom.) 3-2 **V**

**Derniers matchs — Internazionale**
- 31/10 · AC Milan (ext.) 1-3 **D**
- 28/10 · Venezia (ext.) 2-0 **V**
- 25/10 · Fiorentina (dom.) 2-1 **V**
- 21/10 · Shakhtar Donetsk (dom.) 1-0 **V**
- 17/10 · Bologna (ext.) 3-1 **V**

*Source : ESPN (classement et calendrier, cache 24 h).*

## 🧠 Argumentaire du pronostic

- Probabilité réelle **47.2 %** (cote juste 2.12), calculée sur les cotes Pinnacle (modèle de Poisson pour les marchés de buts).
- Cote Betclic non publiée via l'API : **exiger au moins 1.95** sur Betclic (estimation ≈ 1.95 avec sa marge 1N2 de 9.0 % sur ce match).
- Buts attendus pour Feyenoord : 1.8 (ligne 1.5)
- Feyenoord Rotterdam : 2.6 buts marqués / 1.4 encaissés par match

## ⚠️ Point de vigilance

> [!warning] Adversaire en forme : Internazionale VVVVD
> - Marge bookmaker : cote 8.0 % sous la cote juste, espérance négative selon Pinnacle (≈ 8 cts perdus par euro misé en moyenne)

## 💰 Gestion de mise

- Mise conseillée : **1.00 €** (plancher de 1.00 €).
- À titre indicatif : profil **Sweet Spot (Équilibre cote / sécurité)** → 1.5 % de la bankroll = 0.22 € théoriques.
- Mise à plat par profil (pas de Kelly : l'EV est souvent proche de zéro ou négative).
- Ne jamais dépasser la mise conseillée pour « se refaire » ; voir [[Bankroll]].

## Historique des cotes
- 03/11 20:13 — Betclic ≈ 1.95 (estimée, minimum 1.95) · fair 2.119 · EV -7.99 %

## Suivi

- [ ] Pari placé sur Betclic
- Une fois le match terminé : passer `statut` à `GAGNE`, `PERDU`, `REMBOURSE` ou `NON_JOUE`, puis lancer `python bot.py settle`.
- Si la cote ou la mise réellement jouée diffère : ajouter `cote_prise` / `mise_reelle` dans les propriétés.

## Notes personnelles

