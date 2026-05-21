# Baseline Conformance Report

The framework's first fidelity measurement. Per the `plan.md` Charter, the lead
consumer `a_bgt_rsi` tests whether each skill is an **accurate, complete,
low-friction** description of disciplined practice. It cannot test *uplift* —
`a_bgt_rsi` is already maximally disciplined; uplift needs a weaker consumer
(Phase 4).

**Source:** `a_bgt_rsi` — `run_state/week1.run.jsonl` (80 lines, preflight→Day 5),
`git log` (49 commits), `DECISIONS.md` (D-001…D-025).
**Harvests:** H001 (run-log L1–8), H002 (L9–80 + git + decisions).
**Date:** 2026-05-21. **Findings:** 25 in `memory/feedback.jsonl` — 15 confirmed,
8 friction, 2 gap, 0 diverged.

## Per-skill baseline

| Skill | Layer | Conf | Fric | Gap | Baseline status |
|---|---|---|---|---|---|
| resume-state | A | 1 | 0 | 0 | 🟢 confirmed, clean |
| gate-check | A | 3 | 1 | 0 | 🟡 confirmed, 1 friction |
| validate | A | 1 | 2 | 0 | 🟡 confirmed, 2 friction |
| run-log | A | 3 | 1 | 0 | 🟡 confirmed, 1 friction |
| fallback | A | 1 | 1 | 0 | 🟡 confirmed, 1 friction |
| plan-research | B | — | — | — | ⚪ untested (no plan-design in trace) |
| investigate | B | 2 | 0 | 0 | 🟢 confirmed, clean |
| code-review | B | 1 | 0 | 0 | 🟢 confirmed, clean |
| health | B | — | — | — | ⚪ untested (no whole-project checkup in trace) |
| ship | B | 1 | 2 | 0 | 🟡 confirmed, 2 friction |
| experiment | B | 0 | 1 | 0 | 🔴 not used as designed (1 friction, 0 confirmed) |
| auto-experiment | B | — | — | — | ⚪ untested (no autonomous loop yet) |
| repro-check | B | 1 | 0 | 0 | 🟢 confirmed, clean |
| context-save | C | — | — | — | ⚪ untested by design (plan-driven → resume-state) |
| context-restore | C | — | — | — | ⚪ untested by design (→ resume-state) |
| orchestrate | C | 1 | 0 | 1 | 🔴 gap (no parallel-worktree protocol) |
| harvest | C | — | — | — | ⚪ untested (framework-internal; authored Session 2) |
| **decision-log** | — | — | — | 1 | 🔴 absent (proposed skill — a_bgt_rsi shows the discipline) |

## Reading

- **🟢 Fidelity-confirmed, clean** (4): `resume-state`, `investigate`,
  `code-review`, `repro-check`. One more clean harvest → eligible for "hardened"
  (Charter decision rule: 2 consecutive clean harvests).
- **🟡 Confirmed but with open friction** (5): `gate-check`, `validate`,
  `run-log`, `fallback`, `ship`. Broadly accurate, but mis-fits some real use —
  Phase 3 edit candidates.
- **🔴 Gap / not-as-designed** (3): `orchestrate` (gap), `decision-log`
  (absent), `experiment` (exercised, but never via the prescribed
  `experiments.md`).
- **⚪ Untested by `a_bgt_rsi`** (6): `plan-research`, `health`,
  `auto-experiment`, `context-save`, `context-restore`, `harvest`.
  `context-save`/`restore` are untested *correctly* — `a_bgt_rsi` is plan-driven,
  so it uses `resume-state`; the skill's own routing is right. The rest need a
  second consumer (Phase 4).

## What this says about the framework

The execution-discipline core (Layer A) is **descriptively accurate** — every
Layer-A skill is confirmed against real behavior, and the friction findings are
refinements, not refutations. The weak points are at the edges:
parallel-execution orchestration (`orchestrate` gap), decision-logging (no
skill), and research-vertical mechanics (`experiment` / `ship` assume flows
`a_bgt_rsi` does not use).

**`diverged` count is 0** — no skill was contradicted. The framework describes
good practice correctly; where it falls short it is *incomplete*, not *wrong*.
That is the expected result against a fidelity oracle, and it sets up Phase 3:
harden the friction/gap items, then test *uplift* on a weaker consumer.

Open findings feed the `plan.md` backlog. Updated by every `harvest`.
