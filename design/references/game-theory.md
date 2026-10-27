# Game-Theoretic Structure, Population Dynamics & Rankings (`design/references/game-theory.md`)

## When to use
Use when designing or reviewing views of empirical game-theoretic payoffs, multi-agent strategy populations, non-transitive cycles (`Rock-Paper-Scissors` dynamics), Alpha-Rank Markov networks, resource transfer flows, or multi-attribute candidate rankings (`a_bgt_rsi` game-theory experiments and `oracle_system` strategy evaluations).

## Data contract
```json
{
  "strategies": ["S1_Cooperate", "S2_Adaptive", "S3_Exploit"],
  "payoff_matrix": [
    [0.50, 0.20, 0.80],
    [0.80, 0.50, 0.25],
    [0.20, 0.75, 0.50]
  ],
  "games_per_cell": 100,
  "alpha_rank": {
    "stationary_mass": {"S1_Cooperate": 0.28, "S2_Adaptive": 0.44, "S3_Exploit": 0.28},
    "transitions": [
      {"from": "S1_Cooperate", "to": "S2_Adaptive", "fixation_prob": 0.68},
      {"from": "S2_Adaptive", "to": "S3_Exploit", "fixation_prob": 0.64},
      {"from": "S3_Exploit", "to": "S1_Cooperate", "fixation_prob": 0.71}
    ],
    "cycles_detected": [["S1_Cooperate", "S2_Adaptive", "S3_Exploit"]]
  }
}
```

## Canonical views
1. **Pairwise Payoff Heatmap + Directed Response Graph (`Do strategies form a cycle?`):**
   - **Question answered:** Which strategy beats which opponent pairwise, and are there non-transitive `A → B → C → A` cycles hidden by average win rate?
   - **Visual encoding:**
     - Left: `N × N` numeric & color-coded payoff matrix (`tabular-nums`, diverged color scale centered at tie/equilibrium, showing cell payoff + `games_per_cell`).
     - Right: **Alpha-Rank / Omidshafiei Response Graph** where node area/luminance = stationary distribution mass (`π_i`), directed edge thickness = fixation preference (`ρ_{i→j}`), and 3-cycles are highlighted in `--warn`/`--accent` with an explicit cycle callout badge.
2. **Spinning Top Population View (`Transitive Skill vs. Non-Transitive Cycle Width`):**
   - **Question answered:** Does population progress represent genuine transitive skill improvement (vertical height) or sideways cycling within the same tier (horizontal width)?
   - **Visual encoding:** 2D plot with Y-axis = transitive rating / Elo tier and X-axis = non-transitive cycle radius (Czarnecki et al., NeurIPS 2020).
3. **LineUp Multi-Attribute Ranking Table (`Why is this candidate ranked higher?`):**
   - **Question answered:** How do individual attributes (conviction, reproducibility, Brier score, cost, novelty) contribute to a candidate's composite rank, and does the winner change under alternative weights?
   - **Visual encoding:** Table where each row contains a stacked horizontal contribution bar (colored by attribute) alongside exact raw metric columns and interactive weight sliders/presets.
4. **Transfer Flow Matrix (`Cooperative ↔ Exploitative Resource Dynamics`):**
   - **Question answered:** Across multi-round interactions (`lf-game-theory` pattern), who transfers value to whom, and how does Gini inequality evolve?
   - **Visual encoding:** Directed flow matrix paired with a round-by-round Gini / resource trajectory sparkline.

## Interactions
- Selecting a strategy in the Payoff Matrix highlights its outgoing/incoming fixation edges in the Response Graph and its cycle memberships.
- Clicking a weight preset in the LineUp table re-ranks rows in place while showing rank-delta arrows (`↑2`, `↓1`).

## Anti-patterns
- **Don't** display a single scalar leaderboard (Elo or mean payoff) for multiplayer or empirical games without showing the pairwise matrix or cycle indicator; **do** always pair summary ranks with pairwise/cycle structure.
- **Don't** hide weighting and normalization formulas in composite rankings; **do** expose attribute weights and stacked bar contributions (LineUp pattern).

## Deterministic checks
- Payoff matrices declare population size, number of games per cell (`n`), and equilibrium/ranking method (`Alpha-Rank`, `Nash`, `Mean Payoff`).
- Non-transitive cycles (`len(cycles_detected) > 0`) surface an explicit `.cycle-indicator` element in the DOM.

## Sources
- Omidshafiei et al. (2019), *α-Rank: Multi-Agent Evaluation by Evolution* & OpenSpiel (`github.com/google-deepmind/open_spiel`)
- Omidshafiei et al. (2020), *Navigating the Landscape of Multiplayer Games* (`arXiv:2005.01642`)
- Czarnecki et al. (NeurIPS 2020), *Real World Games Look Like Spinning Tops* (`arXiv:2004.09468`)
- LineUp (Gratzl et al., 2013, `github.com/lineupjs/lineupjs`)
- `josephmqiu/game-theory-model`, `Wenyueh/game_theory`, `pfergi42/lf-game-theory` (reviewed `2026-10-27`)
