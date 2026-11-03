---
type: journal
tags: [journal]
---

# 📓 Journal de bord

Retour : [[00 - Dashboard]] · [[Bankroll]] · Modèle d'entrée : [[Modèle - Entrée journal]]

Une entrée par session de paris (la plus récente en haut). Noter surtout ce que les chiffres
ne disent pas : discipline, cotes disparues avant d'avoir pu parier, limitations Betclic,
anomalies du bot.

---

### 2026-11-03 (soir) — Lancement du Challenge 10 €

- **Paper trading** : capital fictif de **10,00 €** géré en autonomie par Claude. Grand livre `betclic-bot/data/ledger.json`.
- Remise à zéro : les 6 fiches de test sont archivées dans `98 - Archives/`.
- Chaque jour à 11 h 30 : règlement automatique sur les scores ESPN, puis 2 à 4 paris simples et 1 Combiné du jour,
  publication du site sur GitHub Pages et un seul message Telegram.
- Mises : 10 % (Safe), 7 % (Sweet Spot), 5 % (Audacieux, Combiné) du solde, plancher 0,50 €, 35 % max par jour.

### 2026-11-03

- **Changement de stratégie** : passage à la [[Stratégie Analyste Contextuel]]. Le filtre EV ≥ 1 % renvoyait 0 pari
  (meilleure EV observée : −5 %, à cause de la marge de Betclic).
- Le bot croise désormais Pinnacle, la cote Betclic et les stats ESPN, puis propose un Top 5 réparti en [[Profils de risque]].
- Réglages : plancher d'EV abaissé à −8 % (≥ 15/30 en stats sous −3.5 %), mise minimale 1 €.
- Marchés : Over/Under, BTTS, double chance, DNB, handicap via un [[Modèle de Poisson]] (l'API publique Betclic n'existe plus) ; Telegram épuré à 4 lignes ; rotation limitée aux compétitions couvertes par ESPN ; coupes d'Europe jugées sur le championnat national.
- Planification : `cron` remplacé par `launchd` (rattrape les scans manqués pendant la veille).

### 2026-11-02

- **Bankroll** : 1 000 € (initiale)
- **Mise en place** : création du coffre, du bot et des règles [[Stratégie Sweet Spot]].
- **À faire** : renseigner `.env`, tester Telegram, premier scan en `--dry-run`.
