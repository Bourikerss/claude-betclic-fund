# CLAUDE.md — Fonds Claude : Challenge 10 € (paper trading Betclic)

Ce dépôt est **à la fois** un coffre Obsidian et le code source d'un bot Python
(`betclic-bot/`). Les règles ci-dessous sont **strictes** : tout changement de code
qui les contredit est un bug. Elles sont implémentées dans
`betclic-bot/src/betclic_bot/rules.py` — ce fichier et ce document doivent
toujours rester synchronisés.

---

## 0. Mode « Paper Trading Autonome » (depuis le 03/11/2026)

- Capital **fictif** de départ : **10,00 €** (`rules.INITIAL_BANKROLL`). Aucun pari réel, aucun réapprovisionnement.
- Le bot gère seul ce capital : il règle les paris terminés, choisit les paris du jour, engage les mises au
  grand livre `betclic-bot/data/ledger.json`, publie le site public (`docs/`, GitHub Pages) et envoie un seul
  message Telegram par jour.
- Les 6 fiches de test d'avant le lancement sont archivées dans `98 - Archives/`.

## 1. Source de données — The Odds API v4

| Paramètre    | Valeur obligatoire              |
|--------------|---------------------------------|
| Endpoint     | `https://api.the-odds-api.com/v4/sports/{sport}/odds` |
| `regions`    | `eu`                            |
| `bookmakers` | `pinnacle,betclic_fr`           |
| `markets`    | `h2h` ; **`h2h,totals` en football** |
| `oddsFormat` | `decimal`                       |

- **Pinnacle** = référence « sharp » : sert uniquement à calculer la probabilité réelle.
- **Betclic (`betclic_fr`)** = seul bookmaker sur lequel on parie.
- **Pourquoi `h2h` seul** (décision du 02/11/2026) : The Odds API ne fournit Betclic qu'en `h2h`
  (vérifié sur NBA et Ligue des Champions). Demander `totals,spreads` faisait facturer 3 crédits
  pour des marchés jamais comparables. Le détecteur sait toujours gérer `totals` et `spreads` :
  les réactiver dans `rules.MARKETS` si Betclic les propose un jour (à vérifier avec le diagnostic du scan).
- L'analyseur note les trois marchés `h2h`, `totals` et `spreads` dès qu'ils sont présents chez
  les deux bookmakers.
- **Football : `totals` demandé** (décision du 03/11/2026, 2 crédits par compétition) : seules les lignes
  Pinnacle servent, à calibrer le modèle de Poisson des marchés dérivés (§3 bis).
- **API publique Betclic** : testée le 03/11/2026, `offer.cdn.begmedia.com` n'existe plus (NXDOMAIN) et
  betclic.fr charge ses cotes en gRPC-web privé. On ne l'utilise pas : pas de scraping d'API privée.
- Ne jamais ajouter d'autre bookmaker ni d'autre marché sans mettre à jour ce fichier.

### 1 bis. Statistiques sportives — ESPN (gratuit, sans clé)

- Module `stats_client.py`, endpoints JSON publics `site.api.espn.com` :
  classement (`/apis/v2/sports/{sport}/{league}/standings`), calendrier d'une équipe
  (`/apis/site/v2/sports/{sport}/{league}/teams/{id}/schedule`), blessures NBA (`…/nba/injuries`).
- Compétitions couvertes : Ligue 1, Premier League, Liga, Serie A, Bundesliga, Ligue des Champions,
  Europa League (football) et NBA. Pour un club, la forme fusionne championnat national et coupe d'Europe.
- **Coupes d'Europe** : classement, bilan et moyennes viennent du **championnat national** du club
  (17 championnats couverts par ESPN, `DOMESTIC_LEAGUES`), et le classement est pondéré par la force du
  championnat (≈ coefficient UEFA : Premier League 1.00 … Ligat HaAl 0.52). Le rang en phase de ligue UEFA
  reste affiché à titre indicatif. Club d'un championnat non couvert (Bulgarie, Pologne…) : classement UEFA.
- Rapprochement des noms The Odds API ↔ ESPN par similarité de mots (minimum des deux sens, seuil 0.75)
  + table d'alias ; un nom ambigu ou inconnu donne « stats indisponibles », jamais une mauvaise équipe.
- Cache disque 24 h (`data/espn_cache/`). En cas de panne ESPN : cache expiré, sinon stats absentes.
  Une panne ESPN ne bloque jamais un scan.

## 2. Multi-sports & quota (500 crédits / mois)

- Les sports sont découverts automatiquement via `GET /v4/sports` (**gratuit**).
  **Seules sont éligibles les compétitions couvertes par ESPN** (`stats_client.ESPN_LEAGUES` : 7 de football
  + NBA) : stats pour l'analyse et scores finaux pour le règlement automatique. Aucun crédit sur les ligues
  secondaires ni sur le tennis (ni stats ni scores ESPN exploitables), décision du 03/11/2026.
- Coût d'un appel `/odds` = `nb marchés × nb régions` : **2 crédits** en football (`h2h,totals`), 1 en NBA.
  Le budget par exécution raisonne sur 2 crédits, avec **1 exécution par jour** (`DAILY_RUNS_PER_DAY`).
- Fenêtre de scan du pipeline quotidien : **24 h** (`DAILY_LOOKAHEAD_HOURS`), du run de 11 h 30 au suivant.
- Avant de payer un appel `/odds`, on vérifie via `GET /v4/sports/{sport}/events` (**gratuit**)
  qu'il existe des matchs dans la fenêtre de scan (`LOOKAHEAD_HOURS`).
- Budget par exécution = `(crédits restants − réserve) / (jours restants dans le mois × exécutions par jour)`.
  Les crédits restants sont lus dans l'en-tête `x-requests-remaining` (source de vérité),
  plafonnés par le budget mensuel local.
- Les sports sont choisis par score = `poids de priorité × couverture Betclic × heures depuis le dernier scan` (rotation, heures plafonnées à 72).
- **Couverture Betclic** : à chaque scan, part des matchs renvoyés où `pinnacle` **et** `betclic_fr` sont présents,
  lissée par moyenne mobile exponentielle (poids 0.5 sur la dernière observation), stockée dans
  `data/quota_state.json`. Inconnue → facteur 1. Plancher à **0.1** : un sport où Betclic est absent
  n'est jamais exclu, il est seulement retesté moins souvent.
- Si le quota est épuisé (`OUT_OF_USAGE_CREDITS`), le scan s'arrête immédiatement.

## 3. Analyste contextuel — Score d'Opportunité et 3 profils

Décision du 03/11/2026 : le filtre « EV ≥ x % contre Pinnacle » renvoyait 0 pari, car la marge
structurelle de Betclic (6 à 8 %) rend l'EV presque toujours négative. Le bot ne cherche plus des
value bets purs : il **classe** chaque issue Betclic et présente le **Top du scan**.
Conséquence assumée : la plupart des paris présentés ont une **EV légèrement négative** selon Pinnacle ;
l'EV réelle est toujours affichée, jamais masquée.

### Score d'Opportunité (/100)

| Pilier | Points | Calcul |
|---|---|---|
| Réalité du marché | 35 | probabilité réelle Pinnacle (dé-viggée) située dans la plage de son profil : SAFE 56 → 75 %, SWEET_SPOT 40 → 56 %, AUDACIEUX 24 → 42 % |
| Compétitivité de la cote | 35 | EV Betclic vs cote juste : −8 % → 0 pt, +5 % ou plus → 35 pts (linéaire) |
| Convergence statistique | 30 | 30 × convergence (0 → 1) ; stats indisponibles → 0.40 (12 pts) |

Convergence selon le marché :
- **1N2 (équipe)** : force = 35 % forme 5 derniers + 25 % bilan sur ce terrain + 20 % classement + 20 % différence/match ;
  convergence = `0.5 + 0.9 × (force équipe choisie − force adversaire)`, bornée [0, 1].
- **Nul** : proximité des deux forces (60 %) + taux de nuls récents (40 %).
- **Over/Under** : total attendu (moyennes saison 60 % / 5 derniers 40 %) comparé à la ligne.
- **Handicap** : écart attendu (différences/match + avantage du terrain) comparé au handicap.

### Profils (conditions toutes obligatoires)

| Profil | Cote Betclic | Autres conditions | Mise |
|---|---|---|---|
| 🛡️ `SAFE` | `1.40 ≤ c < 1.80` | `p ≥ 56 %`, stats **disponibles** et convergence ≥ 0.60 | **10 %** du solde |
| 🎯 `SWEET_SPOT` | `1.80 ≤ c < 2.35` | convergence ≥ 0.50 (si stats disponibles) | **7 %** |
| 🔥 `AUDACIEUX` | `2.35 ≤ c ≤ 3.80` | convergence ≥ 0.40 (si stats disponibles) | **5 %** |

**Plancher d'EV** : `EV = p × c − 1 ≥ −8 %` (abaissé de −3.5 % le 03/11/2026 : à −3.5 %, aucun pari ;
meilleures EV observées entre −4.3 % et −7.4 %). **Filtre de qualité** : si `−8 % ≤ EV < −3.5 %`
(marge Betclic standard), le pilier Statistiques doit valoir **au moins 15/30** — stats ESPN disponibles
et convergence ≥ 0.50. Sans stats (tennis, NFL…), seules les issues à EV ≥ −3.5 % peuvent passer.

Pour tous : marché Pinnacle complet (mêmes issues que Betclic, même ligne pour
totals/spreads) et marge Pinnacle < 12 %. Les matchs déjà commencés sont ignorés.

### 3 bis. Marchés dérivés (football) — modèle de Poisson

The Odds API ne fournit que le 1N2 de Betclic. Pour chaque match de football, `derived.py` calcule la
probabilité juste de :
- **Double chance** (1X, X2) et **Remboursé si nul** : exactes, à partir du 1N2 Pinnacle sans marge ;
- **Plus/Moins de 1.5, 2.5, 3.5 buts**, **buts d'une équipe** (plus/moins de 0.5 et 1.5),
  **les deux équipes marquent** (Oui/Non), **handicap ±1.5** : modèle de Poisson (`poisson.py`) dont les
  buts attendus λ_dom/λ_ext reproduisent le 1N2 et la ligne principale de totals de Pinnacle
  (à défaut de totals, a priori faible sur le total attendu ESPN). Une ligne de totals cotée par Pinnacle
  prime sur le modèle.

La cote Betclic de ces marchés n'est pas connue : elle est **estimée** (cote juste ÷ marge 1N2 Betclic du match),
ce qui sert au profil et au score, et le bot affiche la **cote minimale à exiger** = `cote juste × (1 + MIN_EV)`,
arrondie au centime supérieur. En dessous, le pari sort des règles.

### Sélection du scan

- **2 à 4 paris simples par jour** (au plus 4), **un seul par match** : le marché à la **meilleure convergence statistique**
  (puis au meilleur score) parmi ceux qui passent les filtres.
- Le meilleur de chaque profil est retenu d'abord (s'il existe), puis les matchs par score décroissant.
- **Variété** : au plus **2** paris du même type de marché (1N2, Over/Under, BTTS, DNB, double chance…) ;
  si cela laisse des places vides faute d'autre marché (tennis), on complète sans ce plafond.

Méthode de dé-vigging par défaut : **multiplicative** (proportionnelle) — la plus prudente
sur les favoris. La méthode « power » est disponible via `DEVIG_METHOD=power`.

### 3 ter. Combiné du jour

- Chaque jour, **1 Combiné du jour** : 2 ou 3 sélections sur des matchs **différents** (et absents des paris
  simples du jour), cote totale entre **1.70 et 2.40**.
- Sélection éligible : cote 1.15 – 1.75, probabilité Pinnacle ≥ 60 %, EV ≥ −8 %, stats ESPN disponibles et
  convergence ≥ 0.60. Le combiné retenu maximise la convergence moyenne, puis la probabilité combinée.
- Pas de combiné possible : un **pari Fun** (meilleur Audacieux d'un autre match) le remplace.
- Les marges se multiplient dans un combiné : son EV est affichée dans la fiche.

## 4. Gestion de mise — proportionnelle au solde

- Mise = **solde actuel** (grand livre, lu une fois en début de run) × % du profil, au centime :
  SAFE **10 %**, SWEET_SPOT **7 %**, AUDACIEUX **5 %**, COMBINÉ **5 %**. Plancher absolu **0,50 €**, pas de plafond :
  si le solde double, les mises doublent (demande du 03/11/2026).
- **Plafond journalier** : jamais plus de **35 %** du solde disponible en début de journée engagés le même jour ;
  une mise qui dépasse est réduite au reliquat, ou abandonnée si le reliquat est sous 0,50 €.
- Un match déjà engagé (pari en cours) n'est jamais rejoué.

## 4 bis. Grand livre et règlement automatique

- `betclic-bot/data/ledger.json` (`ledger.py`) : solde initial, chaque opération (`DEPOT`, `MISE` débitée,
  `GAIN` / `REMBOURSEMENT` crédités, `PERTE`) avec le solde après opération, et l'historique complet des paris
  (sélections = `legs`). Indicateurs : solde disponible, capital réalisé (initial + profits réglés), ROI
  (profit / initial), yield (profit / misé réglé), taux de réussite, drawdown max du capital réalisé.
- `auto_settle.py`, au début de chaque run : scores finaux sur le scoreboard ESPN de la compétition
  (`/apis/site/v2/sports/{sport}/{league}/scoreboard?dates=AAAAMMJJ`, J et J−1, cache 1 h), rapprochement
  des équipes par similarité de noms, puis évaluation du marché (1N2, double chance, DNB, BTTS, Over/Under,
  buts d'une équipe, handicap). Combiné : perdu dès qu'une sélection est perdue ; une sélection remboursée vaut 1.
  Match reporté/annulé → remboursé ; introuvable 3 jours après le coup d'envoi → remboursé.
- Le règlement met à jour le grand livre **et** la fiche Obsidian (`statut`, `profit`, `score_final`, `regle_le`).

## 5. Intégration Obsidian

Chaque pari retenu crée (ou met à jour) **une fiche d'analyse** dans `02 - Paris Détectés/` avec ce
frontmatter YAML minimal (clés obligatoires, dans cet ordre) :

```yaml
sport: Football
ligue: Premier League
match: Arsenal vs Chelsea
date: 2026-11-03T21:00          # heure de Paris
marche: Vainqueur du match
selection: Arsenal
profil: SAFE                    # SAFE | SWEET_SPOT | AUDACIEUX
score_confiance: 74             # Score d'Opportunité /100
cote_betclic: 1.65
fair_odd_pinnacle: 1.684
probabilite_reelle: 59.37       # en %
ev_percent: -2.04               # en %
mise_recommandee: 1.0           # en € (10 % d'un solde de 10 €)
statut: EN_ATTENTE
profit: 0
```

- Le corps de la fiche contient, dans cet ordre : le pari (cotes, probabilité, EV, marges, détail du score),
  **📊 Contexte sportif** (classement, bilan, forme des 5 derniers, série, domicile/extérieur,
  moyennes marquées/encaissées, différence, absents, derniers matchs des deux équipes),
  **🧠 Argumentaire du pronostic** (3 à 4 puces générées), **⚠️ Point de vigilance** (risque principal
  identifié dans les chiffres), **💰 Gestion de mise**, l'historique des cotes et le suivi.
- Marché dérivé : `cote_betclic` = **cote minimale à exiger** ; compléments `type_marche`,
  `cote_source: estimee | betclic` et `cote_estimee`. Noter la cote réellement prise dans `cote_prise`.
- Liens `[[Sport]]`, `[[Ligue]]`, `[[Stratégie Analyste Contextuel]]`, `[[Profils de risque]]` et
  `[[Score d'Opportunité]]` pour la Vue Graphique. Les notes hub sont créées dans `04 - Sports & Ligues/`.
- **Mise à jour** : la note est identifiée par le champ `id`. Le bot ne réécrit **jamais** les
  valeurs de détection (`cote_betclic`, `mise_recommandee`, …) : il met à jour
  `cote_betclic_actuelle`, `ev_actuel_percent`, `derniere_maj` et ajoute une ligne à
  « Historique des cotes ». Une note dont le `statut` n'est plus `EN_ATTENTE` n'est plus jamais modifiée par le scan.
- Valeurs de `statut` : `EN_ATTENTE`, `GAGNE`, `PERDU`, `REMBOURSE`. Le règlement est **automatique**
  (§4 bis) : ne plus modifier le statut à la main. `python bot.py settle` le lance à la demande.
- Le Combiné du jour a sa propre fiche (`AAAA-MM-JJ - Combiné du jour.md`, `profil: COMBINE`).
- **Telegram : un seul message par jour** (`notifier.format_daily`), envoyé en fin de pipeline :

  ```
  💰 PORTEFEUILLE CLAUDE : 10,42 € (+0,42 € | ROI : +4,2 %)
  📅 Hier : 1G - 1P (+0,15 €)

  🎯 LES PARIS DU JOUR

  🛡️ Porto vs Napoli (Ligue des Champions · mer. 21h00)
  👉 Porto @ 1,85 — Mise : 1,00 €
  📊 Porto : 6V-0N-1D à domicile, forme VVNVV contre DVNVD pour Napoli

  🧩 COMBINÉ DU JOUR @ 2,04 — Mise : 0,50 €
  • PSV Eindhoven vs Club Brugge : Les 2 équipes marquent : Oui (@ 1,40)
  • Inter vs Roma : Plus de 1.5 buts (@ 1,46)

  🌐 Suivi en direct : https://<compte>.github.io/<dépôt>/
  ```
  Portefeuille = capital réalisé (solde initial + profits réglés) ; « Hier » = paris réglés pendant ce run.
  Pour un marché dérivé, la cote affichée et engagée est la cote minimale à exiger (§3 bis).

## 5 bis. Site public (GitHub Pages)

- `build_web.py` génère `docs/` (racine du dépôt) : `index.html` (données du grand livre injectées en JSON),
  `style.css`, `app.js` (sources dans `betclic-bot/src/betclic_bot/web/`) et `.nojekyll`.
- Direction artistique « journal financier » : fond crème `#F6F4F0` / carbone `#0F1012`, filets 1 px, gains
  `#166534`, pertes `#991B1B`, en cours ocre ; Instrument Serif (titres), Plus Jakarta Sans (interface),
  JetBrains Mono `tabular-nums` (chiffres). Interdits : dégradés violet/bleu, glassmorphism, ombres néon,
  police Inter, emojis dans les titres de cartes.
- Contenu : en-tête « Fonds Claude · Capital 10 € » et indicateurs, courbe du capital (SVG, survol/toucher),
  positions du jour (bordereaux), grand livre filtrable, analytique par profil et par type de marché.

## 5 ter. Automatisation macOS et publication

- Agent `launchd` `~/Library/LaunchAgents/fr.bot-sporif.betclic-scan.plist` (copie : `betclic-bot/deploy/`) :
  **une seule exécution par jour à 11 h 30**, `python bot.py daily`, qui enchaîne
  `auto_settle` → `scan` (+ engagement des mises) → `build_web` → `git_sync` → message Telegram.
  Chaque étape est isolée : une panne n'empêche pas les suivantes. Si le Mac dormait, launchd lance le
  pipeline au réveil. Journal : `betclic-bot/data/bot.log`. Pas de `cron`.
- `git_sync.py` : `git add -A`, `commit -m "update: bilan et paris du JJ/MM/AAAA"`, `push origin main`.
  **Garde-fous** : publication bloquée si un `.env` est indexé ou si une valeur secrète du `.env`
  (clé API, token, chat id) apparaît dans le diff. `.gitignore` racine strict (`.env`, `.venv/`, caches, logs).

## 6. Conventions de code

- Python 3.9+ (`from __future__ import annotations`), code et commentaires en français.
- Aucun secret dans le code : tout passe par `betclic-bot/.env` (voir `.env.example`).
- Toute modification d'une règle métier doit être accompagnée d'un test dans `betclic-bot/tests/`.
- Lancer les tests : `cd betclic-bot && python -m pytest`.
