---
type: strategie
tags: [strategie]
---

# Stratégie Analyste Contextuel (Quantitatif & Contextuel)

Retour : [[00 - Dashboard]] · Détails : [[Score d'Opportunité]] · [[Profils de risque]]

## Pourquoi ce changement (03/11/2026)

L'ancienne [[Stratégie Sweet Spot]] ne retenait que les paris à EV positive contre [[Pinnacle]].
Or [[Betclic]] prend une marge de **6 à 8 %** sur chaque marché : sur les premiers scans, la meilleure
EV observée était de −5 %, donc **0 pari** à chaque passage.

Le bot ne cherche donc plus seulement des « value bets » purs. Il **classe** toutes les issues Betclic
d'un scan et présente chaque jour de matchs les meilleures opportunités, de la plus sûre à la plus risquée.

## Les 3 sources croisées

1. **Le marché** : la probabilité réelle d'après Pinnacle sans marge ([[Dé-vigging Pinnacle]]).
2. **Le prix** : à quel point la cote Betclic est proche de la cote juste ([[Expected Value (EV)]]).
3. **Le terrain** : les statistiques ESPN (forme, domicile/extérieur, classement, moyennes, blessures NBA).

Le bot ne regarde pas que le 1N2. En football, il évalue aussi Over/Under, Les deux équipes marquent,
Double chance, Remboursé si nul, buts d'une équipe et handicap, grâce au [[Modèle de Poisson]].
Pour ces marchés, il donne la cote minimale à exiger sur Betclic.

Chaque issue reçoit un [[Score d'Opportunité]] sur 100. Elle est rangée dans un des [[Profils de risque]] selon sa cote.

## Ce qu'il faut garder en tête

> [!warning] EV négative assumée
> La plupart des paris présentés ont une EV **négative** selon Pinnacle (entre −10 % et 0 %). Sous −3.5 %, le pari
> n'est gardé que si les stats ESPN le soutiennent nettement (≥ 15/30).
> Les statistiques ne rendent pas un pari rentable à elles seules : le marché Pinnacle les intègre déjà.
> Le bot sélectionne les **meilleurs paris disponibles** chez Betclic. Ce ne sont pas des paris gagnants
> à coup sûr. Les fiches affichent toujours l'EV réelle.

- Les mises sont **petites et à plat** par profil (voir [[Profils de risque]]) pour limiter la casse.
- Le vrai juge est le **ROI par profil** sur plusieurs centaines de paris : à suivre dans le [[00 - Dashboard]].
- Les paris à EV positive (rares) restent signalés comme « vraie value » dans l'argumentaire.

## Implémentation

`betclic-bot/src/betclic_bot/` : `stats_client.py` (ESPN), `poisson.py` et `derived.py` (marchés dérivés),
`analyzer.py` (score et profils),
`notifier.py` (Telegram), `rules.py` (constantes). Voir [[Architecture du Bot]].
