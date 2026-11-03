---
type: strategie
tags: [strategie, bankroll]
---

# Profils de risque

Partie de : [[Stratégie Analyste Contextuel]] · Score : [[Score d'Opportunité]] · Suivi : [[Bankroll]]

| Profil | Cote Betclic | Conditions | Mise |
|---|---|---|---|
| 🛡️ **SAFE** (base solide) | 1.40 – 1.80 | Proba Pinnacle ≥ 56 %, stats **disponibles** et convergence ≥ 60 % | **10 %** du solde |
| 🎯 **SWEET SPOT** (équilibre) | 1.80 – 2.35 | Convergence ≥ 50 % si stats disponibles | **7 %** |
| 🔥 **AUDACIEUX** (belle cote) | 2.35 – 3.80 | Convergence ≥ 40 % si stats disponibles | **5 %** |

Pour tous les profils : EV ≥ −8 % ([[Expected Value (EV)]]), marché [[Pinnacle]] complet et marge < 12 %.
Si l'EV est entre −8 % et −3.5 %, le pilier Stats doit valoir au moins **15/30** (voir [[Score d'Opportunité]]).

## Sélection d'un scan

- **2 à 4 paris simples par jour** + 1 Combiné du jour, **un seul pari par match** : le marché dont les stats convergent le plus (1N2, Over/Under,
  Les deux équipes marquent, Double chance, Remboursé si nul, handicap… voir [[Modèle de Poisson]]).
- Le meilleur de chaque profil passe en premier, s'il existe. On complète ensuite par score.
- **Variété** : au plus 2 paris du même type de marché par scan.
- Un jour sans match couvert peut ne rien donner. C'est normal.

## Mises : proportionnelles au solde (Challenge 10 €)

| Profil | % du solde | Avec 10 € | Avec 20 € |
|---|---|---|---|
| 🛡️ Safe | 10 % | 1,00 € | 2,00 € |
| 🎯 Sweet Spot | 7 % | 0,70 € | 1,40 € |
| 🔥 Audacieux | 5 % | 0,50 € | 1,00 € |
| 🧩 Combiné du jour | 5 % | 0,50 € | 1,00 € |

- **Plancher 0,50 €**, aucun plafond : la mise suit le solde à la hausse comme à la baisse.
- **Plafond journalier 35 %** du solde disponible : au-delà, la mise est réduite ou le pari abandonné.
- Pas de Kelly : avec une EV ≤ 0, le [[Quarter Kelly]] conseillerait de ne rien miser.
- Voir [[Fonds Claude - Challenge 10 €]].

## Suivi par profil

```dataview
TABLE WITHOUT ID
  profil AS "Profil",
  length(rows) AS "Paris réglés",
  round(sum(rows.profit), 2) AS "Profit €",
  round(sum(rows.mise_recommandee), 2) AS "Misé €"
FROM "02 - Paris Détectés"
WHERE type = "pari" AND contains(list("GAGNE", "PERDU", "REMBOURSE"), statut)
GROUP BY profil
```
