---
type: strategie
tags: [strategie, maths]
---

# Modèle de Poisson (marchés internes au match)

Partie de : [[Stratégie Analyste Contextuel]] · Score : [[Score d'Opportunité]] · Référence : [[Pinnacle]]

## Pourquoi

The Odds API ne fournit que le 1N2 de [[Betclic]]. L'API publique de Betclic n'existe plus : testée le 03/11/2026,
le site charge ses cotes par un canal privé. Pour proposer **Over/Under, Les deux équipes marquent, Double chance,
Remboursé si nul et Handicap**, le bot calcule lui-même leur probabilité juste.

## Calibrage

Chaque équipe marque selon une loi de Poisson : λ_dom buts attendus à domicile, λ_ext à l'extérieur.
On choisit (λ_dom, λ_ext) pour reproduire au mieux :
1. le 1N2 [[Pinnacle]] sans marge ([[Dé-vigging Pinnacle]]) ;
2. la ligne principale « Plus/Moins de 2.5 » de Pinnacle (demandée en football) ;
3. à défaut, le total attendu d'après ESPN : (attaque dom. + défense ext.)/2 + (attaque ext. + défense dom.)/2.

$$P(\text{score } i\text{–}j) = \frac{e^{-\lambda_{dom}}\lambda_{dom}^{i}}{i!}\times\frac{e^{-\lambda_{ext}}\lambda_{ext}^{j}}{j!}$$

## Marchés calculés

| Marché | Probabilité |
|---|---|
| Double chance 1X / X2 | p(1) + p(N), p(N) + p(2) : exact, Pinnacle |
| Remboursé si nul | p(1) / (p(1) + p(2)) : exact, Pinnacle |
| Plus/Moins de 1.5 / 2.5 / 3.5 buts | Poisson (une ligne cotée par Pinnacle prime) |
| Buts d'une équipe : plus/moins de 0.5 / 1.5 | Poisson |
| Les deux équipes marquent : Oui/Non | Poisson |
| Handicap −1.5 / +1.5 | Poisson (victoire par 2 buts ou plus) |

## Cote affichée

> [!warning] La cote Betclic de ces marchés n'est pas connue
> Le bot l'**estime** en appliquant la marge 1N2 de Betclic sur ce match. Ce n'est qu'une estimation.
> Il affiche surtout la **cote minimale à exiger** : `cote juste × 0.92` (EV ≥ −8 %).
> Sur Betclic, ne prendre le pari que si la cote affichée est **au moins** celle-là, puis noter la cote réelle
> dans `cote_prise`.

Limite connue : le Poisson simple sous-estime légèrement les nuls (≈ 2 points). C'est sans effet sur
Double chance et Remboursé si nul, qui viennent directement de Pinnacle.
