---
type: strategie
tags: [strategie, maths, bankroll]
---

# Quarter Kelly (plafonné à 3 %)

> [!warning] Plus utilisé depuis le 03/11/2026
> Avec une EV ≤ 0, Kelly conseille de ne rien miser. Le bot applique désormais une **mise à plat par profil** :
> voir [[Profils de risque]]. Cette note reste valable pour un pari à EV positive.

Partie de : [[Stratégie Sweet Spot]] · Entrée : [[Expected Value (EV)]] · Suivi : [[Bankroll]]

## Critère de Kelly

Fraction de bankroll qui maximise la croissance à long terme :

$$f^* = \frac{b\,p - q}{b} \qquad b = c - 1,\quad q = 1 - p$$

## Pourquoi un quart ?

Le Kelly complet suppose que `p` est **exacte**. Or elle est estimée (via [[Dé-vigging Pinnacle]]).
Surestimer `p` avec Kelly complet mène à des mises trop fortes et à des drawdowns violents.
Le **Quarter Kelly** (`0.25 × f*`) conserve ≈ 44 % de la croissance optimale avec une
variance divisée par ~16.

## Règle finale

$$\text{mise} = \text{bankroll} \times \min(0.25 \times f^*,\ 3\ \%)$$

Le plafond de **3 %** empêche une seule erreur d'estimation de peser trop lourd.

## Exemple

- `p` = 53.97 %, cote = 1.95 → `b` = 0.95
- `f*` = (0.95 × 0.5397 − 0.4603) / 0.95 = **5.52 %**
- Quarter Kelly = **1.38 %** → avec 1 000 € de bankroll : **13.80 €**

## Bankroll utilisée

Le bot calcule la bankroll courante = `bankroll_initiale` de la note [[Bankroll]] + somme
des `profit` des paris réglés. Les mises suivent donc automatiquement les gains et pertes.

Code : `betclic-bot/src/betclic_bot/value.py`
