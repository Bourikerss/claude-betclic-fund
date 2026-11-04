---
type: sport
tags: [hub/sport]
---

# Basketball

Hub du sport — relié au [[00 - Dashboard]] et à la [[Stratégie Analyste Contextuel]].

## Ligues

```dataview
LIST FROM "04 - Sports & Ligues" WHERE type = "ligue" AND sport = "Basketball"
```

## Paris

```dataview
TABLE WITHOUT ID file.link AS "Pari", profil AS "Profil", ligue AS "Ligue", date AS "Date", cote_betclic AS "Cote", score_confiance AS "Score", statut AS "Statut", profit AS "Profit €"
FROM "02 - Paris Détectés"
WHERE sport = "Basketball"
SORT date DESC
```
