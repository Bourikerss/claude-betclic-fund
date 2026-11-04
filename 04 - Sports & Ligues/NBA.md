---
type: ligue
sport: Basketball
tags: [hub/ligue]
---

# NBA

Compétition de [[Basketball]].

```dataview
TABLE WITHOUT ID file.link AS "Pari", profil AS "Profil", date AS "Date", cote_betclic AS "Cote", score_confiance AS "Score", statut AS "Statut", profit AS "Profit €"
FROM "02 - Paris Détectés"
WHERE ligue = "NBA"
SORT date DESC
```
