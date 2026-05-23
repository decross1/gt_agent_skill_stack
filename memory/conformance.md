# Conformance Report

The framework's fidelity measurement. Per the `plan.md` Charter, the lead
consumer `a_bgt_rsi` tests whether each skill is an **accurate, complete,
low-friction** description of disciplined practice. It cannot test *uplift* —
`a_bgt_rsi` is already maximally disciplined; uplift needs a weaker consumer
(Phase 4).

**Source:** `a_bgt_rsi` — `run_state/week1.run.jsonl`, `git log`, `DECISIONS.md`.
**Harvests:** H001–H002 baseline (preflight→Day 4), H003 (Day 5), H004 (Day-5 ops, 0 findings).
**Updated:** 2026-05-22. **Findings:** 29 in `memory/feedback.jsonl` —
17 confirmed, 10 friction, 2 gap, **0 diverged**.

## Per-skill conformance

| Skill | Layer | Conf | Fric | Gap | Status |
|---|---|---|---|---|---|
| resume-state | A | 1 | 0 | 0 | 🟢 confirmed, clean |
| gate-check | A | 3 | 1 | 0 | 🟡 confirmed, 1 friction |
| validate | A | 3 | 2 | 0 | 🟡 confirmed; 2 friction addressed S9 |
| run-log | A | 3 | 2 | 0 | 🟡 confirmed, 2 friction |
| fallback | A | 1 | 1 | 0 | 🟡 confirmed, 1 friction |
| plan-research | B | — | — | — | ⚪ untested (no plan-design in trace) |
| investigate | B | 2 | 0 | 0 | 🟢 confirmed, clean |
| code-review | B | 1 | 0 | 0 | 🟢 confirmed, clean |
| health | B | — | — | — | ⚪ untested |
| ship | B | 1 | 2 | 0 | 🟡 confirmed, 2 friction |
| experiment | B | 0 | 1 | 0 | 🔴 not used as designed |
| auto-experiment | B | — | — | — | ⚪ untested |
| repro-check | B | 1 | 1 | 0 | 🟡 confirmed, 1 friction |
| context-save | C | — | — | — | ⚪ untested by design (→ resume-state) |
| context-restore | C | — | — | — | ⚪ untested by design (→ resume-state) |
| orchestrate | C | 1 | 0 | 1 | 🟡 gap addressed S7, re-harvest pending |
| harvest | C | — | — | — | ⚪ untested (framework-internal) |
| decision-log | C | — | — | 1 | 🟡 created S8 — gap addressed, untested |

## Reading

- **🟢 Fidelity-confirmed, clean** (3): `resume-state`, `investigate`,
  `code-review`.
- **🟡 Confirmed but with open friction** (6): `gate-check`, `validate`,
  `run-log`, `fallback`, `ship`, `repro-check`.
- **🔴 / addressed gap** (3): `orchestrate` (gap addressed S7 — re-harvest
  pending to mark hardened), `decision-log` (skill created S8 — re-harvest
  pending), `experiment` (exercised, but never via the prescribed
  `experiments.md`).
- **⚪ Untested by `a_bgt_rsi`** (6): `plan-research`, `health`,
  `auto-experiment`, `context-save`, `context-restore`, `harvest`. The rest
  need a weaker second consumer (Phase 4).

## What this says about the framework

`diverged` count remains **0** across three harvests — no skill has been
contradicted by real disciplined work. The framework describes good practice
correctly; where it falls short it is *incomplete*, not *wrong*. H003 added a
notable signal: a friction finding can be **confirmed by a later harvest** —
`a_bgt_rsi` resolved a mis-specified criterion exactly the way H002's
`validate` friction finding predicted (amend the plan, never coerce, record
forward), evidence that the friction findings point the right way.

## Hardening log (Phase 3)

- **S7 — 2026-05-22 — `orchestrate`**: parallel-worktree execution protocol
  added (file-boundary allow-lists, mock isolation, pre-merge boundary
  verification, `--no-ff` merges, completion sentinels). Resolves the H002
  `orchestrate` gap. Marked *hardened* once a re-harvest shows no regression.
- **S8 — 2026-05-22 — `decision-log`**: new skill created (mandatory
  Alternatives + Reversibility + supersedes-chains), resolving the H002
  `decision-log` gap; the framework's `DECISIONS.md` template updated to match.
- **S9 — 2026-05-22 — `validate`**: added a "When the criterion itself is
  wrong" protocol and a tightly-scoped `partial_pass` verdict, resolving both
  H002 `validate` friction findings. (`run-log`'s status-enum side stays open.)

Open findings feed the `plan.md` backlog. Updated by every `harvest`.
