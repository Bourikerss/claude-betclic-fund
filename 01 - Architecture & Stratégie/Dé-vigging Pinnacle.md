---
type: strategie
tags: [strategie, maths]
---

# Dé-vigging Pinnacle

Partie de : [[Stratégie Analyste Contextuel]] · Source : [[Pinnacle]]

## Le problème : la marge (vig)

Un bookmaker transforme les probabilités en cotes **après** avoir ajouté sa marge.
La somme des probabilités implicites dépasse donc 100 % :

$$\text{overround} = \sum_i \frac{1}{c_i} > 1$$

Exemple 1N2 Pinnacle : Arsenal 1.80 · Nul 3.90 · Chelsea 4.60

| Issue | Cote | 1 / cote |
|---|---|---|
| Arsenal | 1.80 | 55.56 % |
| Nul | 3.90 | 25.64 % |
| Chelsea | 4.60 | 21.74 % |
| **Total** | | **102.94 %** → marge ≈ 2.9 % |

## Méthode multiplicative (par défaut)

On répartit la marge proportionnellement :

$$p_i = \frac{1/c_i}{\sum_j 1/c_j}$$

Arsenal : 55.56 / 102.94 = **53.97 %** → cote juste = 1 / 0.5397 = **1.853**

C'est la méthode la plus **prudente** pour la stratégie : elle a tendance à sous-estimer
légèrement la probabilité des favoris, donc à sous-estimer l'[[Expected Value (EV)]] des favoris.

## Méthode « power » (option)

On cherche l'exposant `k` tel que :

$$\sum_i \left(\frac{1}{c_i}\right)^k = 1 \quad\Rightarrow\quad p_i = \left(\frac{1}{c_i}\right)^k$$

Elle reporte plus de marge sur les outsiders (biais favori/outsider), ce qui donne une
probabilité un peu plus haute aux favoris → plus de paris détectés, moins conservateur.
Activation : `DEVIG_METHOD=power` dans `betclic-bot/.env`.

## Garde-fous dans le code

- Le marché Pinnacle doit contenir **exactement** les mêmes issues que celui de [[Betclic]]
  (pas de dé-vigging d'un 2 voies comparé à un 1N2).
- Les lignes totals/spreads doivent être identiques.
- Marge > 12 % → données jugées aberrantes, marché ignoré.

Code : `betclic-bot/src/betclic_bot/devig.py`
