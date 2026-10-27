# Scientific Experiments, Hypothesis Trees & QD Archives (`design/references/experiments.md`)

## When to use
Use when designing or reviewing views for scientific experiment comparison, parameter sweeps, ablation studies, Quality-Diversity (QD) archives, or research insight provenance (`a_bgt_rsi` `:5173`, `oracle_system` HOURGLASS strategy comparisons, `agent_system` `verify_skill_lift.py` receipts). Fixture: `design/evals/experiments_fixture.json`.

## Data contract
Combines **Sakana AI-Scientist-v2** Hypothesis Tree nodes, **pyribs** QD archive cells, **Aim** run metadata, and **Trrack** insight provenance:
```json
{
  "hypothesis_tree": [
    {
      "node_id": "exp-01",
      "parent_id": "exp-00",
      "h0": "Adding backward qualification predicates does not reduce false switches.",
      "h1": "ReHarness backward qualification (n_eff >= 5) reduces false_switch rate by >= 15%.",
      "controlled_diff": "Enable hourglass/reharness_lessons.py scope narrowing",
      "seed": 42,
      "env_hash": "sha256:9c41b2",
      "eval_version": "eval-v2.1",
      "metrics": {
        "brier_score": {"mean": 0.142, "ci95": 0.011, "unit": "Brier (lower better)"},
        "false_switch_rate": {"mean": 0.04, "ci95": 0.015, "unit": "proportion"}
      },
      "status": "supported"
    }
  ],
  "qd_archive": {
    "x_axis": "exploration_entropy",
    "y_axis": "cost_efficiency",
    "cells": [
      {"x_bin": 2, "y_bin": 3, "best_id": "exp-01", "score": 0.86}
    ]
  }
}
```

## Canonical views
1. **Sakana Hypothesis & Ablation Tree (`How did this experimental result evolve from its baseline?`):**
   - **Question answered:** What was the exact controlled diff from the parent run, what were `H0`/`H1`, and which branches succeeded, failed, or were pruned?
   - **Visual encoding:** Directed tree (top-to-bottom or left-to-right) where each node shows `node_id`, `controlled_diff` badge, primary metric delta vs. parent (`Δ -0.031 Brier`), and status color (`supported` `--ok`, `refuted` `--bad`, `inconclusive` `--warn`).
2. **Aligned Run Comparison Table with Uncertainty (`Which experiment improved the outcome, and is the comparison valid?`):**
   - **Question answered:** Across repeated seeds, does candidate `B` beat baseline `A` under the *same* `eval_version` and dataset?
   - **Visual encoding:**
     - **Compatibility Guardrail (Blocking):** Group runs by `eval_version` and `env_hash`. If a user selects runs with different `eval_version` values, render a prominent `--warn` banner (`⚠ Incompatible evaluation versions: eval-v2.0 vs eval-v2.1 — metrics are not directly comparable`).
     - **Uncertainty & Sample Size:** Always display `mean ± ci95` (or `min..max`), `n_seeds`, and explicit units (`ms`, `Brier`, `%`).
3. **pyribs 2D Quality-Diversity (QD) Niche Heatmap (`Which behavioral niches have been explored?`):**
   - **Question answered:** Where in behavioral measure space do our best candidates sit, and which regions are unexplored?
   - **Visual encoding:** 2D grid (`x_axis × y_axis`) where filled cells encode best score via luminance (`--surface` → `--accent`) and empty cells carry a distinct hatched/muted `unexplored` treatment (`0` runs, never `UNKNOWN`).
4. **Trrack Insight Provenance Card (`How did we reach this conclusion?`):**
   - **Question answered:** Can another researcher or auditor reproduce this exact chart and conclusion?
   - **Visual encoding:** Compact footer/drawer recording `claim`, `author_type` (`human` | `agent`), `dataset/eval_version`, `commit_sha`, active filters, and `supersedes` link.

## Interactions
- Group-by parameter (`controlled_diff`, `eval_version`, `model`) and toggle delta-from-baseline mode.
- Clicking a QD heatmap cell or Hypothesis Tree node highlights the corresponding row in the Aligned Run Comparison Table.

## Anti-patterns
- **Don't** plot or rank runs from incompatible `eval_version` schemas on the same axis without a warning; **do** partition or flag incompatible evaluation versions explicitly.
- **Don't** report point estimates (`0.84`) without sample size (`n=5 seeds`) and uncertainty (`±0.02`); **do** show confidence intervals or seed dispersion.
- **Don't** leave unexplored QD grid cells indistinguishable from zero-score failed runs; **do** distinguish `unexplored (0 runs)` from `evaluated (score = 0.0)`.

## Deterministic checks
- Every experiment metric column displays units and sample size (`n`) or CI.
- Incompatible `eval_version` rows trigger a visible `.eval-mismatch-warning` element.

## Sources
- Sakana AI, `AI-Scientist-v2` (`arXiv:2504.08066`, `github.com/SakanaAI/AI-Scientist-v2`) — Agentic Tree-Search & Hypothesis Tree state machine
- `pyribs` (`github.com/icaros-usc/pyribs`) — `grid_archive_heatmap` QD niche encoding
- Aim (`github.com/aimhubio/aim`) & HiPlot (`github.com/facebookresearch/hiplot`) — parameter grouping & parallel coordinates
- Trrack (`github.com/Trrack/trrackjs`, Cutler et al., 2020) — insight provenance records
