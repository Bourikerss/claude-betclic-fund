---
type: strategie
tags: [strategie, maths]
---

# Score d'Opportunité (/100)

Partie de : [[Stratégie Analyste Contextuel]] · Profils : [[Profils de risque]]

## Les 3 piliers

| Pilier | Points | Ce qui est mesuré |
|---|---|---|
| 🎲 Réalité du marché | 35 | Probabilité réelle [[Pinnacle]], placée dans la plage de son profil |
| 💶 Compétitivité de la cote | 35 | Écart cote [[Betclic]] / cote juste : EV −10 % → 0 pt, +5 % → 35 pts |
| 📊 Convergence statistique | 30 | Les stats ESPN confirment-elles le pari ? (0 → 1) |

### 1. Marché (35 pts)

Plages de probabilité réelle, de 0 au maximum : SAFE 56 → 75 %, SWEET SPOT 40 → 56 %, AUDACIEUX 24 → 42 %.
À cote égale, l'issue la plus probable de son profil marque plus.

### 2. Cote (35 pts)

$$\text{points} = 35 \times \frac{EV + 10\,\%}{5\,\% + 10\,\%}\quad\text{(borné à [0, 35])}$$

Voir [[Expected Value (EV)]]. Une issue sous −10 % d'EV est écartée : Betclic s'y sert trop.
Entre −10 % et −3.5 % (marge Betclic standard), il faut **au moins 15/30 en stats** : le pari n'est gardé
que si la forme, le classement et les moyennes le soutiennent vraiment.

### 3. Stats (30 pts)

- **Vainqueur** (le classement d'un club de coupe d'Europe est celui de son championnat national, pondéré
  par la force de ce championnat) : force de chaque équipe = 35 % forme des 5 derniers + 25 % bilan sur ce terrain
  + 20 % classement + 20 % différence de buts/points par match.
  Convergence = 0.5 + 0.9 × (force de l'équipe choisie − force de l'adversaire).
- **Match nul** : équipes de force proche + taux de nuls récents.
- **Double chance / Remboursé si nul** : comme le vainqueur, l'équipe couverte ne doit pas perdre.
- **Les deux équipes marquent** : part des 10 derniers matchs où chaque équipe a marqué et encaissé.
- **Buts d'une équipe** : son attaque contre la défense adverse, comparée à la ligne.
- **Plus/Moins** : total attendu (moyennes saison 60 %, 5 derniers 40 %) comparé à la ligne.
- **Handicap** : écart attendu (différences par match + avantage du terrain) comparé au handicap.
- **Stats indisponibles** (tennis, NFL…) : 0.40, soit 12 pts. C'est une note prudente, pas neutre.

## Lecture

| Score | Lecture |
|---|---|
| ≥ 70 | Les trois signaux sont alignés |
| 50 – 69 | Correct, un pilier plus faible |
| < 50 | Le meilleur disponible, sans plus |

Constantes : `betclic-bot/src/betclic_bot/rules.py` (`SCORE_WEIGHTS`, `PROB_SCORE_RANGE`, `MIN_EV`).
