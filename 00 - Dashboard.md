---
type: dashboard
tags: [hub/dashboard]
---

# 📊 Fonds Claude — Dashboard (Challenge 10 €)

> [!tip] Navigation
> **Stratégie** : [[Stratégie Analyste Contextuel]] · [[Score d'Opportunité]] · [[Profils de risque]] · [[Modèle de Poisson]] · [[Dé-vigging Pinnacle]] · [[Expected Value (EV)]]
> **Technique** : [[Architecture du Bot]] · [[Gestion du Quota API]] · [[Pinnacle]] · [[Betclic]]
> **Challenge** : [[Fonds Claude - Challenge 10 €]] · site public dans `docs/` (GitHub Pages)
> **Suivi** : [[Bankroll]] · [[Journal de bord]] · [[Modèle - Fiche Pari|Modèle de fiche]] · Archive : [[Stratégie Sweet Spot]]

> [!warning] Prérequis
> Plugin communautaire **Dataview** installé, avec « Enable JavaScript Queries » activé.

## 📈 Indicateurs clés

```dataviewjs
const bets = dv.pages('"02 - Paris Détectés"').where(p => p.type === "pari");
const settled = bets.where(p => ["GAGNE", "PERDU", "REMBOURSE"].includes(p.statut));
const won = settled.where(p => p.statut === "GAGNE").length;
const lost = settled.where(p => p.statut === "PERDU").length;
const stakeOf = (p) => Number(p.mise_reelle ?? p.mise_recommandee ?? 0);
const staked = settled.where(p => p.statut !== "REMBOURSE").array().reduce((s, p) => s + stakeOf(p), 0);
const profit = settled.array().reduce((s, p) => s + Number(p.profit ?? 0), 0);
const initial = Number(dv.page("03 - Bilan & Bankroll/Bankroll")?.bankroll_initiale ?? 0);
const avg = (arr, key) => arr.length ? arr.reduce((s, p) => s + Number(p[key] ?? 0), 0) / arr.length : 0;
const fmt = (n) => n.toLocaleString("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

dv.table(["Indicateur", "Valeur"], [
  ["💰 Bankroll actuelle", `**${fmt(initial + profit)} €** (initiale ${fmt(initial)} €)`],
  ["📈 Profit net", `${profit >= 0 ? "+" : ""}${fmt(profit)} €`],
  ["🔁 ROI (yield)", staked ? `${fmt(profit / staked * 100)} %` : "—"],
  ["✅ Réussite", (won + lost) ? `${fmt(won / (won + lost) * 100)} % (${won} G / ${lost} P)` : "—"],
  ["⏳ En attente", bets.where(p => p.statut === "EN_ATTENTE").length],
  ["🎯 Paris proposés", bets.length],
  ["⭐ Score moyen", bets.length ? `${fmt(avg(bets.array(), "score_confiance"))} / 100` : "—"],
  ["📐 EV moyenne (selon Pinnacle)", `${fmt(avg(bets.array(), "ev_percent"))} %`],
]);
```

## 🧭 Performance par profil

```dataviewjs
const profiles = [["SAFE", "🛡️ Safe"], ["SWEET_SPOT", "🎯 Sweet Spot"], ["AUDACIEUX", "🔥 Audacieux"], ["COMBINE", "🧩 Combiné"]];
const bets = dv.pages('"02 - Paris Détectés"').where(p => p.type === "pari");
const fmt = (n) => n.toLocaleString("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
dv.table(["Profil", "Proposés", "Réglés", "Réussite", "Misé €", "Profit €", "ROI", "Cote moy.", "EV moy."],
  profiles.map(([key, label]) => {
    const all = bets.where(p => p.profil === key).array();
    const settled = all.filter(p => ["GAGNE", "PERDU", "REMBOURSE"].includes(p.statut));
    const won = settled.filter(p => p.statut === "GAGNE").length;
    const lost = settled.filter(p => p.statut === "PERDU").length;
    const staked = settled.filter(p => p.statut !== "REMBOURSE")
      .reduce((s, p) => s + Number(p.mise_reelle ?? p.mise_recommandee ?? 0), 0);
    const profit = settled.reduce((s, p) => s + Number(p.profit ?? 0), 0);
    const mean = (k) => all.length ? all.reduce((s, p) => s + Number(p[k] ?? 0), 0) / all.length : 0;
    return [label, all.length, settled.length,
      (won + lost) ? `${fmt(won / (won + lost) * 100)} %` : "—",
      fmt(staked), `${profit >= 0 ? "+" : ""}${fmt(profit)}`,
      staked ? `${fmt(profit / staked * 100)} %` : "—",
      all.length ? fmt(mean("cote_betclic")) : "—",
      all.length ? `${fmt(mean("ev_percent"))} %` : "—"];
  }));
```

## ⏳ Paris en attente

```dataview
TABLE WITHOUT ID
  file.link AS "Pari",
  profil AS "Profil",
  score_confiance AS "Score",
  marche AS "Marché",
  selection AS "Sélection",
  ligue AS "Ligue",
  date AS "Coup d'envoi",
  cote_betclic AS "Cote",
  probabilite_reelle AS "Proba %",
  ev_percent AS "EV %",
  mise_recommandee AS "Mise €"
FROM "02 - Paris Détectés"
WHERE type = "pari" AND statut = "EN_ATTENTE"
SORT date ASC
```

## 🏆 Profit par sport

```dataview
TABLE WITHOUT ID
  sport AS "Sport",
  length(rows) AS "Paris réglés",
  round(sum(rows.profit), 2) AS "Profit €",
  round(sum(rows.mise_recommandee), 2) AS "Misé €"
FROM "02 - Paris Détectés"
WHERE type = "pari" AND contains(list("GAGNE", "PERDU", "REMBOURSE"), statut)
GROUP BY sport
SORT sum(rows.profit) DESC
```

## 🧾 Derniers paris réglés

```dataview
TABLE WITHOUT ID file.link AS "Pari", profil AS "Profil", statut AS "Statut", cote_betclic AS "Cote", mise_recommandee AS "Mise €", profit AS "Profit €"
FROM "02 - Paris Détectés"
WHERE type = "pari" AND statut != "EN_ATTENTE"
SORT date DESC
LIMIT 15
```

## 📅 Bilans mensuels

```dataview
LIST FROM "03 - Bilan & Bankroll" WHERE type = "bilan" SORT mois DESC
```

## ⚙️ Commandes du bot

| Action | Commande (depuis `betclic-bot/`) |
|---|---|
| Cycle quotidien complet | `.venv/bin/python bot.py daily` |
| Scanner et engager les paris du jour | `.venv/bin/python bot.py scan` |
| Tester sans écrire de fiche | `.venv/bin/python bot.py scan --dry-run` |
| Régler les paris terminés (ESPN) | `.venv/bin/python bot.py settle` |
| Régénérer le site | `.venv/bin/python bot.py build-web` |
| État du quota | `.venv/bin/python bot.py quota` |
| Sports éligibles (gratuit) | `.venv/bin/python bot.py sports` |
| Journal des scans automatiques | `tail -n 50 data/bot.log` |
