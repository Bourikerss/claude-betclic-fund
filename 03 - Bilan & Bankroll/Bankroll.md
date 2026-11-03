---
type: bankroll
bankroll_initiale: 10.00
date_debut: 2026-11-03
mode: paper_trading
devise: EUR
tags:
  - bankroll
---

# 💰 Bankroll — Fonds Claude (capital fictif 10 €)

Retour : [[00 - Dashboard]] · Règle de mise : [[Profils de risque]]

> [!important] Source de vérité : le grand livre
> Depuis le 03/11/2026, le bot gère en autonomie un **capital fictif de 10,00 €** (paper trading, aucun pari réel).
> Chaque mouvement est inscrit dans `betclic-bot/data/ledger.json` : dépôt initial, mises débitées, gains crédités,
> solde après opération. Le site public reprend ces chiffres. Le tableau ci-dessous les retrouve à partir des fiches.

## Règles de gestion

- Mise proportionnelle au **solde actuel** : 🛡️ SAFE **10 %** · 🎯 SWEET SPOT **7 %** · 🔥 AUDACIEUX **5 %** ·
  🧩 COMBINÉ **5 %**, plancher **0,50 €** et aucun plafond : si le solde double, les mises doublent (voir [[Profils de risque]]).
- Jamais plus de **35 %** du solde disponible engagés sur une même journée.
- Aucun réapprovisionnement : le défi se joue avec les 10 € de départ.
- Stop-loss psychologique : si la bankroll baisse de 30 %, pause et revue de la [[Stratégie Analyste Contextuel]].

## Évolution (paris réglés)

```dataviewjs
const initial = Number(dv.current().bankroll_initiale ?? 0);
const bets = dv.pages('"02 - Paris Détectés"')
  .where(p => p.type === "pari" && ["GAGNE", "PERDU", "REMBOURSE"].includes(p.statut))
  .sort(p => p.date, "asc");
let br = initial;
const rows = bets.array().map(p => {
  br += Number(p.profit ?? 0);
  return [p.file.link, p.statut, `${Number(p.profit ?? 0) >= 0 ? "+" : ""}${Number(p.profit ?? 0).toFixed(2)} €`, `${br.toFixed(2)} €`];
});
dv.paragraph(`**Bankroll actuelle : ${br.toFixed(2)} €** (${((br / initial - 1) * 100).toFixed(2)} %)`);
dv.table(["Pari", "Statut", "Profit", "Bankroll"], rows);
```

## Bilans mensuels

```dataview
LIST FROM "03 - Bilan & Bankroll" WHERE type = "bilan" SORT mois DESC
```
