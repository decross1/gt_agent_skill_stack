# Product Context: Agentic Research Lab Interfaces

**Status:** Canonical product brief for UI/UX planning, implementation, and review across the portfolio (`agent_system`, `oracle_system`, `a_bgt_rsi`).
**Updated:** 2026-10-27

## 1. Mission & Users

The portfolio operates as an autonomous and human-stewarded research lab across four live web surfaces:

1. **Oracle Portal (`:8790`, `oracle_system`)** — Unified command center for cross-project continuity, 2D spatial Essence Atlas (`oracle_view`), multi-agent fleet coordination (`argon`, `codex`, `opus`, `sonnet`), quota burn envelopes, daily deltas/musings, and the 5-pipe continuity matrix.
2. **Oracle Memory Cockpit (`:8765`, `oracle_system`)** — Append-only event ledger (`state/events.jsonl`), charter & governance status, and HOURGLASS strategy/dropbox inspection.
3. **Nara Research Lab UI (`:5173` frontend / `:8700` backend, `a_bgt_rsi`)** — Empirical game-theoretic and recursive self-improvement (RSI) research dashboard: Now/Operations view, Evidence Ladder (`L0`→`L5`), experiment runs, and apparatus supervision.
4. **Framework Brain (`:5180`, `agent_system`)** — Dev-time observation, skill-conformance (`harvest`), anomaly/drift detection, and proposal-review graph (`dashboard.html`, `graph.html`, `activity.html`).

The primary user (the lab owner) requires **high-density visual interfaces paired with concise, proximate explanations**. Screens must make it effortless to see what agents are doing, how beliefs and memory evolve over time, what scientific experiments establish, and where human judgment or gate clearance is needed.

---

## 2. Central Questions by Domain

Every screen or panel must begin by stating which of these questions it answers:

| Area | Primary Questions the Interface Must Answer |
|---|---|
| **Agent runtime** | What is running, waiting, retrying, or complete? Where did execution diverge? Which agent or loop needs human attention right now, and why? |
| **Agent memory** | What does an agent currently believe? Which source episode established it? When was it valid (`valid_from` → `valid_to`), and what superseded it (`expired_at`)? |
| **Context and evidence** | Which entities, sources, hypotheses, decisions (`D-NNN`), and experiments are connected? What typed edge (`Semantic`, `Temporal`, `Causal`, `Entity`) connects them? |
| **Scientific experiments** | What controlled change occurred between runs? What evidence supports the result? Is the lift repeatable across seeds and comparable across evaluation versions? |
| **Analytics** | Which parameter combinations explain an outcome? What tradeoffs (cost, latency, Brier score, survival rate) remain after filtering? |
| **Game theory** | Which strategies outperform which opponents? Are there non-transitive cycles (`A > B > C > A`) or population dynamics hidden by a scalar ranking? |
| **Research insights** | How did we reach a conclusion? Can an auditor or human revisit the exact dataset, commit hash, filter state, and evidence chain? |

---

## 3. Core Product & Terminology Conventions

1. **Chat/CLI as Control Panel, Spatial/Analytical Surface as Workspace:**
   - Do not render primary system state as flat chat transcripts or raw `<dl>` key-value dumps.
   - Separate the **Control / Filter Strip** (compact top or side bar) from the **Analytical / Spatial Workspace** (timelines, bitemporal scrubbers, spatial canvases, structured comparison tables, payoff matrices).
2. **Epistemic Provenance is First-Class (`AGENTS.md` Rule 3):**
   - Every material claim, edge, or summary metric must distinguish its epistemic status:
     - `observed` — directly verified from an immutable ledger, process table, or git commit.
     - `inferred` — derived by deterministic rules over incomplete observations.
     - `synthesized` — aggregated across multiple records or domains.
     - `proposed` — candidate change awaiting human or steward review.
     - `speculative` — unverified hypothesis or exploratory branch.
     - `oracle_taste` — structural resonance or curiosity bridge from the owner's Essence profile.
     - `unknown` — genuinely absent from available sources (must state *why* it is unknown, e.g., `"No heartbeat recorded in spawn.jsonl"`).
3. **Honest Missingness vs. Raw `"UNKNOWN"` Spam:**
   - Never paint a dashboard with dozens of identical `"UNKNOWN"` badges.
   - Distinguish five distinct non-nominal states:
     - **`0` (Explicit Zero):** Measured and found to be zero (e.g., `0` survivors at Ladder rung `L3`). Render as `0`, never `—` or `UNKNOWN`.
     - **`unmeasured` / `not tracked`:** The schema or producer does not emit this field (e.g., passive quota burn when no active telemetry probe is configured). Render muted (`--text-faint`) with a concise tooltip or inline reason (`"Not instrumented"`).
     - **`stale`:** A prior observation exists, but its age exceeds the freshness window. Show the last known value + relative age (`"2h ago · stale"`).
     - **`failed` / `degraded`:** A check ran and failed. Show the specific failure code or reason (`--bad`).
     - **`unknown`:** Reserve strictly for unexpected missing state that requires investigation.
4. **Release & Provenance Visibility:**
   - Every live UI surface is governed by `oracle_ui_release.py` and exposes its running commit vs. repo `HEAD` via `/api/release` or `RELEASE.json`.
   - Derived views (`oracle_view`, Brain pages, Portal insights) are read-only projections; canonical authority always resides in `state/events.jsonl`, `state/charter.json`, and `DECISIONS.md`.
