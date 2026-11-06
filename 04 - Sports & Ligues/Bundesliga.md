---
type: ligue
sport: Football
tags: [hub/ligue]
---

# Bundesliga

Compétition de [[Football]].

```dataview
TABLE WITHOUT ID file.link AS "Pari", profil AS "Profil", date AS "Date", cote_betclic AS "Cote", score_confiance AS "Score", statut AS "Statut", profit AS "Profit €"
FROM "02 - Paris Détectés"
WHERE ligue = "Bundesliga"
SORT date DESC
```
