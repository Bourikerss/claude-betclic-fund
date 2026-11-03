---
type: strategie
tags: [strategie, maths]
---

# Expected Value (EV)

Partie de : [[Stratégie Sweet Spot]] · Entrée : [[Dé-vigging Pinnacle]] · Suite : [[Quarter Kelly]]

## Formule

Pour une probabilité réelle `p` (issue de [[Pinnacle]] sans marge) et une cote [[Betclic]] `c` :

$$EV = p \times c - 1$$

C'est le gain moyen **par euro misé** si l'on répétait le pari à l'infini.

## Exemple

- Probabilité réelle Arsenal : 53.97 % (cote juste 1.853)
- Cote Betclic : 1.95

$$EV = 0.5397 \times 1.95 - 1 = +5.24\ \%$$

Équivalent : la cote Betclic est 5.2 % au-dessus de la cote juste (`1.95 / 1.853 − 1`).

## Usage dans la stratégie

| Condition | Seuil |
|---|---|
| EV minimale pour être présenté | **≥ −8 %** (≥ 15/30 en stats si < −3.5 %) |
| EV donnant le maximum de points « cote » | **≥ +5 %** |

Depuis le 03/11/2026 ([[Stratégie Analyste Contextuel]]), l'EV ne filtre plus : elle note la **compétitivité
de la cote** dans le [[Score d'Opportunité]]. La marge de Betclic (6 à 8 %) rend l'EV presque toujours négative,
et l'estimation Pinnacle comporte elle-même une erreur de l'ordre de 1 à 2 %.

## Lecture des résultats

- L'EV moyenne des paris détectés est affichée dans le [[00 - Dashboard]].
- Le ROI réel (profit / mises) doit converger vers l'EV moyenne sur un grand échantillon.
  Un ROI durablement très inférieur signale un problème (cotes plus disponibles, mauvaise exécution).

Code : `betclic-bot/src/betclic_bot/value.py`
