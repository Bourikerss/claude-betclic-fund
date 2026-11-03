---
sport: Football
ligue: Ligue 1
match: Équipe A vs Équipe B
date: {{date:YYYY-MM-DD}}T21:00
marche: Vainqueur du match
selection: Équipe A
profil: SAFE
score_confiance: 70
cote_betclic: 1.65
fair_odd_pinnacle: 1.62
probabilite_reelle: 61.73
ev_percent: 1.85
mise_recommandee: 2
statut: EN_ATTENTE
profit: 0
type: pari
id: manuel-{{date:YYYYMMDDHHmm}}
mise_percent: 2
mise_theorique: 2
score_marche: 10.2
score_cote: 22.7
score_stats: 21
convergence_stats: 0.7
cote_pinnacle: 1.58
marge_pinnacle_percent: 2.5
marge_betclic_percent: 6.8
bankroll_reference: 100
cote_betclic_actuelle: 1.65
ev_actuel_percent: 1.85
detecte_le: {{date:YYYY-MM-DD}}T{{time:HH:mm}}
derniere_maj: {{date:YYYY-MM-DD}}T{{time:HH:mm}}
liens: ["[[Football]]", "[[Ligue 1]]"]
tags: [pari, manuel, profil/safe]
---

# 🛡️ SAFE — Équipe A vs Équipe B : Équipe A

> [!info] Pari saisi manuellement le {{date:DD/MM/YYYY}}
> **Profil** : Safe (Base solide) · **Score d'Opportunité** : **70/100**
> **Sport** : [[Football]] · **Ligue** : [[Ligue 1]] · **Méthode** : [[Stratégie Analyste Contextuel]] · [[Profils de risque]]

> [!note] Mode d'emploi du modèle
> Les fiches générées par le bot suivent exactement cette structure.
> Pour un pari manuel : insérer ce modèle (plugin Modèles), déplacer la note dans `02 - Paris Détectés/`,
> puis remplacer les valeurs. Les 15 premières propriétés sont **obligatoires** (voir `CLAUDE.md`).

## 🎯 Le pari

| Indicateur | Valeur |
|---|---|
| Marché | Vainqueur du match |
| Sélection | **Équipe A** |
| Cote Betclic | **1.65** |
| Cote Pinnacle (brute) | 1.58 |
| Cote juste Pinnacle (sans marge) | 1.620 |
| Probabilité réelle | 61.73 % |
| Expected Value | +1.85 % |
| Marge Betclic sur ce marché | 6.80 % |

**[[Score d'Opportunité]] : 70/100** = marché 10.2/35 + cote 22.7/35 + stats 21/30 (convergence 70 %)

## 📊 Contexte sportif

| | Équipe A | Équipe B |
|---|---|---|
| Classement | 2/18 | 12/18 |
| Bilan saison | 7V-2N-1D | 3V-3N-4D |
| Forme (5 derniers, dernier à droite) | `VVNVV` | `DNDVD` |
| Série en cours | 2 victoires | 1 défaite |
| Domicile (dom.) / Extérieur (ext.) | dom. 4V-1N-0D | ext. 1V-1N-3D |
| Buts marqués / match | 2.10 | 1.00 |
| Buts encaissés / match | 0.80 | 1.50 |
| Différence / match | 1.30 | -0.50 |
| Absents / incertains | — | — |

## 🧠 Argumentaire du pronostic

- Pinnacle, le marché de référence, estime la probabilité réelle à **61.7 %** (cote juste 1.62) : Betclic propose **1.65**.
- Cote Betclic **+1.9 %** au-dessus de la cote juste, malgré une marge de 6.8 % sur ce marché : une vraie value.
- Équipe A : forme VVNVV (13/15 pts sur les 5 derniers matchs)
- Équipe A à domicile cette saison : 4V-1N-0D

## ⚠️ Point de vigilance

> [!warning] Adversaire en forme : …

## 💰 Gestion de mise

- Profil **Safe (Base solide)** → **2 %** de la bankroll : **2.00 €**.
- Mise à plat par profil (pas de Kelly : l'EV est souvent proche de zéro ou négative).
- Ne jamais dépasser la mise conseillée pour « se refaire » ; voir [[Bankroll]].

## Historique des cotes
- {{date:DD/MM}} {{time:HH:mm}} — Betclic **1.65** · fair 1.620 · EV +1.85 %

## Suivi

- [ ] Pari placé sur Betclic
- Une fois le match terminé : passer `statut` à `GAGNE`, `PERDU`, `REMBOURSE` ou `NON_JOUE`, puis lancer `python bot.py settle`.
- Si la cote ou la mise réellement jouée diffère : ajouter `cote_prise` / `mise_reelle` dans les propriétés.

## Notes personnelles

