---
type: strategie
tags: [strategie]
---

# Stratégie Sweet Spot (Safe + Bonne Cote)

Retour : [[00 - Dashboard]]

> [!warning] Stratégie archivée le 03/11/2026
> Remplacée par la [[Stratégie Analyste Contextuel]] : le filtre ci-dessous renvoyait 0 pari, à cause de la marge
> structurelle de Betclic. Le nom « Sweet Spot » survit dans un des [[Profils de risque]] (cotes 1.80 – 2.35).
> Cette note est conservée pour l'historique.

## Idée

[[Pinnacle]] est le bookmaker le plus « sharp » du marché : ses cotes, une fois la marge
retirée ([[Dé-vigging Pinnacle]]), sont la meilleure estimation publique de la
probabilité réelle d'un événement. Quand [[Betclic]] propose une cote **supérieure** à
cette cote juste, le pari a une [[Expected Value (EV)]] positive.

Le « Sweet Spot » ajoute des contraintes de **sécurité** : on ne joue que des issues
probables (≈ favoris ou quasi pile-ou-face) à cote raisonnable, pour limiter la variance.

## Les 3 filtres (tous obligatoires)

| # | Filtre | Règle |
|---|---|---|
| 1 | Probabilité réelle | `p ≥ 52 %` **ou** (`p ≥ 48 %` **et** `EV > 4 %`) |
| 2 | Cote Betclic | `1.40 < cote < 2.50` (bornes exclues) |
| 3 | Valeur | `EV ≥ 1 %` |

> [!note] Seuils élargis le 03/11/2026
> Avant : `1.50 < cote < 2.25` et `EV ≥ 2.5 %`. Élargis pour détecter plus d'opportunités,
> au prix d'une marge de sécurité plus faible (voir [[Expected Value (EV)]]).

Pourquoi ces bornes :
- **Cote > 1.40** : en dessous, l'EV absolue en euros est minuscule et le moindre écart d'estimation l'annule.
- **Cote < 2.50** : au-delà, la variance explose (taux de réussite < 40 %) — ce n'est plus « safe ».
- **Proba ≥ 52 %** : on gagne plus souvent qu'on ne perd → séries perdantes plus courtes.
- **Dérogation 48 %** : acceptée seulement si l'avantage est fort (EV > 4 %).

## Mise

[[Quarter Kelly]] plafonné à **3 %** de la bankroll — voir [[Bankroll]].

## Marchés couverts

- `h2h` — vainqueur du match (1N2 au football) : **seul marché scanné**, car c'est le seul que
  The Odds API fournit pour Betclic (voir [[Gestion du Quota API]]).
- `totals` (plus/moins) et `spreads` (handicap) : gérés par le code mais désactivés. Les lignes
  devront être **identiques** chez Pinnacle et Betclic (ex. Over 2.5 vs Over 2.5).

## Implémentation

Voir [[Architecture du Bot]] et la règle source `betclic-bot/src/betclic_bot/rules.py`.
Le quota d'API limite le nombre de sports scannés : [[Gestion du Quota API]].

## Limites connues

- Les cotes Betclic bougent : la cote affichée dans la fiche est celle du **moment du scan**.
- Betclic limite les comptes gagnants : rester discret (mises arrondies, pas uniquement des value bets).
- La rentabilité se juge sur **plusieurs centaines** de paris, pas sur une semaine.
