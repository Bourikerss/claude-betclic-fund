---
type: strategie
tags: [strategie, bankroll, paper-trading]
---

# Fonds Claude — Challenge 10 €

Retour : [[00 - Dashboard]] · Méthode : [[Stratégie Analyste Contextuel]] · Mises : [[Profils de risque]] · Suivi : [[Bankroll]]

## Le principe

Depuis le 03/11/2026, Claude gère **seul** un capital **fictif** de **10,00 €** (paper trading, aucun pari réel).
Objectif : le faire fructifier jour après jour, en publiant tous ses comptes.

## Chaque jour à 11 h 30

1. **Règlement** des paris terminés d'après les scores finaux ESPN : gagné, perdu ou remboursé.
2. **Scan** des compétitions couvertes par ESPN : 1N2, Over/Under, BTTS, double chance, DNB, handicap
   ([[Modèle de Poisson]]).
3. **Paris du jour** : 2 à 4 paris simples variés + 1 **Combiné du jour** (2 – 3 sélections, cote 1.70 – 2.40)
   ou, à défaut, un pari Fun.
4. **Grand livre** `betclic-bot/data/ledger.json` : chaque mise débitée, chaque gain crédité, solde après opération.
5. **Site public** régénéré dans `docs/` puis poussé sur GitHub Pages.
6. **Un message Telegram** : portefeuille, bilan de la veille, paris du jour et lien du site.

## À garder en tête

> [!warning] Espérance négative
> La marge de Betclic (6 à 10 %) rend la plupart des paris perdants en moyenne selon Pinnacle, et un combiné
> multiplie ces marges. Le défi documente honnêtement ce que donne la meilleure sélection possible.
> Ce n'est pas une promesse de gain.
