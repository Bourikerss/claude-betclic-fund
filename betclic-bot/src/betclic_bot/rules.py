"""Règles métier de l'analyste contextuel (3 profils).

Miroir exact de CLAUDE.md (racine du coffre). Ne jamais modifier une valeur ici
sans mettre CLAUDE.md à jour et ajouter un test.
"""

# --- Source : The Odds API v4 -------------------------------------------------
REGIONS = "eu"
SHARP_BOOK = "pinnacle"
TARGET_BOOK = "betclic_fr"
BOOKMAKERS = (SHARP_BOOK, TARGET_BOOK)
# Marchés demandés à l'API. Betclic n'est fourni qu'en h2h par The Odds API
# (constaté le 02/11/2026 sur NBA et LDC) : demander totals/spreads triplait le coût pour rien.
MARKETS = ("h2h",)
# Football : on demande aussi les `totals` Pinnacle pour calibrer le modèle de Poisson
# (Betclic n'en fournit pas via l'API ; décision du 03/11/2026, 2 crédits par compétition).
SOCCER_MARKETS = ("h2h", "totals")
# Marchés que le détecteur sait comparer entre Pinnacle et Betclic.
SUPPORTED_MARKETS = ("h2h", "totals", "spreads")

# --- Quota ---------------------------------------------------------------------
MONTHLY_CREDITS = 500
# Coût d'un appel /odds = nb marchés × nb régions. Le budget raisonne sur le cas le plus cher (football).
COST_PER_ODDS_CALL = len(SOCCER_MARKETS) * 1


def markets_for(sport_key: str) -> tuple:
    return SOCCER_MARKETS if sport_key.startswith("soccer_") else MARKETS

# --- Analyste contextuel : 3 profils (CLAUDE.md §3, décision du 03/11/2026) ------
# Le filtre « EV ≥ x % » renvoyait 0 pari (marge Betclic structurelle de 6 à 8 %).
# On classe désormais les issues Betclic par Score d'Opportunité et on retient le Top du scan.
PROFILE_SAFE = "SAFE"
PROFILE_SWEET_SPOT = "SWEET_SPOT"
PROFILE_AUDACIEUX = "AUDACIEUX"
PROFILES = (PROFILE_SAFE, PROFILE_SWEET_SPOT, PROFILE_AUDACIEUX)
PROFILE_COMBINE = "COMBINE"  # Combiné du jour (paper trading)

# Plage de cotes Betclic par profil : borne basse incluse, borne haute exclue (sauf la dernière).
ODD_RANGES = {
    PROFILE_SAFE: (1.40, 1.80),
    PROFILE_SWEET_SPOT: (1.80, 2.35),
    PROFILE_AUDACIEUX: (2.35, 3.80),  # 3.80 inclus
}
SAFE_MIN_FAIR_PROB = 0.56
# Convergence statistique minimale (0 → 1). SAFE exige des stats disponibles.
MIN_STATS_SCORE = {PROFILE_SAFE: 0.60, PROFILE_SWEET_SPOT: 0.50, PROFILE_AUDACIEUX: 0.40}
# Fourchette d'EV brute acceptée : Betclic peut être sous Pinnacle (marge), mais pas trop.
# Plancher abaissé à −8 % le 03/11/2026 : à −3.5 %, 0 pari (meilleures EV observées −4.3 % à −7.4 %).
MIN_EV = -0.08
# Entre MIN_EV et ce seuil (marge Betclic « standard »), le pari n'est gardé que si les stats le soutiennent.
STANDARD_MARGIN_EV = -0.035
MIN_STATS_POINTS_LOW_EV = 15  # sur 30 : stats disponibles et convergence ≥ 0.50
EV_SCORE_CEILING = 0.05  # EV ≥ 5 % → note de cote maximale
# Mise à plat selon le profil, en fraction de la bankroll.
# --- Paper trading « Challenge 10 € de Claude » (décision du 03/11/2026) -------------
INITIAL_BANKROLL = 10.00
# Mise = solde actuel (ledger.json, lu en début de run) × % du profil, au centime, plancher 0,50 €.
# Proportionnelle et sans plafond : si le solde double, les mises doublent (demande du 03/11/2026).
STAKE_PCT = {PROFILE_SAFE: 0.10, PROFILE_SWEET_SPOT: 0.07, PROFILE_AUDACIEUX: 0.05, PROFILE_COMBINE: 0.05}
STAKE_MIN = 0.50
DAILY_EXPOSURE_MAX = 0.35  # jamais plus de 35 % du solde disponible engagés sur une même journée

# Score d'Opportunité sur 100 = marché + cote + stats.
SCORE_WEIGHTS = {"marche": 35, "cote": 35, "stats": 30}
# Plage de probabilité réelle qui va de 0 à plein score « marché », par profil.
PROB_SCORE_RANGE = {PROFILE_SAFE: (0.56, 0.75), PROFILE_SWEET_SPOT: (0.40, 0.56), PROFILE_AUDACIEUX: (0.24, 0.42)}
NEUTRAL_STATS_SCORE = 0.40  # stats indisponibles (tennis, NFL…) : note prudente

# Marchés dérivés (modèle de Poisson calibré sur Pinnacle) : Betclic ne les publie pas via l'API.
# On affiche la cote minimale à exiger sur Betclic = cote juste × (1 + MIN_EV).
DERIVED_MARKETS = ("double_chance", "dnb", "btts", "totals", "team_totals", "spreads")
DERIVED_TOTAL_LINES = (1.5, 2.5, 3.5)
DERIVED_TEAM_LINES = (0.5, 1.5)
DERIVED_SPREAD = 1.5  # handicap ±1.5 (victoire par 2 buts d'écart ou plus)
POISSON_DEFAULT_TOTAL = 2.6  # buts par match si ni Pinnacle totals ni stats ESPN

# Sélection par scan
MAX_PICKS_PER_SCAN = 4  # paris simples par jour (2 à 4), au plus une issue par match
MIN_PICKS_PER_SCAN = 2
MAX_PICKS_PER_MARKET = 2  # variété : au plus 2 paris du même type de marché

# --- Garde-fous données ------------------------------------------------------------
MAX_PINNACLE_OVERROUND = 1.12

# --- Statuts des fiches Obsidian ------------------------------------------------------
STATUT_EN_ATTENTE = "EN_ATTENTE"
STATUTS_REGLES = ("GAGNE", "PERDU", "REMBOURSE", "NON_JOUE")

# --- Combiné du jour --------------------------------------------------------------------
COMBO_MIN_LEGS = 2
COMBO_MAX_LEGS = 3
COMBO_MIN_ODD = 1.70
COMBO_MAX_ODD = 2.40
COMBO_LEG_MIN_ODD = 1.15
COMBO_LEG_MAX_ODD = 1.75
COMBO_LEG_MIN_PROB = 0.60       # sélections « solides »
COMBO_LEG_MIN_STATS = 0.60      # convergence ESPN minimale (stats obligatoires)

# --- Pipeline quotidien -----------------------------------------------------------------
DAILY_RUNS_PER_DAY = 1
DAILY_LOOKAHEAD_HOURS = 24       # paris du jour : matchs avant le prochain run (11 h 30 → 11 h 30)
