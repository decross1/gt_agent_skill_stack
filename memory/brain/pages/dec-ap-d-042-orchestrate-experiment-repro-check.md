---
slug: "dec-ap-d-042-orchestrate-experiment-repro-check"
type: "decision"
date: "2026-06-09"
source: "a_bgt_rsi/DECISIONS.md"
---

# D-042 — orchestrate / experiment / repro-check / plan-research are intentionally REFERENCED-ONLY (harvest re-flags resolved)

_apparatus decision_

**Date locked.** 2026-06-09. Agent-governance harness cycle; serial-integrator wiring under the human's 2026-06-09 attestation.

**Relates to.** [D-037](#d-037--authorize-dynamic-workflows-amend-d-030s-single-session-constraint) — Dynamic Workflows + the verify gate are the substitution this entry records.

**Decision.** The four framework skills `orchestrate`, `experiment`, `repro-check`, and `plan-research` are, in this apparatus, **intentionally referenced-only** — their function is met by the **Dynamic-Workflow + verify-gate substitution** (D-037), not by invoking the skills as named procedures. `orchestrate`'s role-decomposition / parallel-execution job is carried by the `Workflow` primitive under the §"Dynamic Workflow discipline"; `experiment` / `repro-check` are carried by the run log + `DECISIONS.md` + per-experiment harness dirs (the project deliberately keeps no separate `experiments.md` ledger); `plan-research` is carried by the daily `human/sessions/` working note + the staged plan. Harvest passes should **stop re-flagging** these as gaps/frictions: the divergence is a ratified design choice, recorded here so the harvest watermark has a durable reference instead of re-surfacing it each cycle.

**Verified harvest mapping** (against `agent_system/memory/feedback.jsonl`, this cycle): `orchestrate` -> **H002** (confirmed L23/L24, friction L33 under H005), **H005**, **H007** (confirmed L42); `experiment` -> **H002** (friction L21, the "allow the run log to be the experiment ledger" finding); `repro-check` -> **H002** (confirmed L22) and **H003** (friction L29, the real-vs-mock check); `plan-research` -> **not harvest-flagged** (zero `feedback.jsonl` hits — listed here for completeness, not because a finding exists). This entry dispositions those findings as *won't-fix-by-design* on the consumer side; they may still inform framework-side skill edits, which is the framework's call, not the apparatus's.

**Why referenced-only, not adopted.** Adopting the skills as literal procedures would duplicate machinery the apparatus already has in a more discipline-bound form: the Workflow primitive is bounded/observable/resumable (D-037) where `orchestrate`'s hand-rolled worktree matrices were the very thing D-030 retired; a separate `experiments.md` is a parallel store the project rejected in favor of the single append-only run log; `plan-research`'s artifacts already live in the session note. The skills remain *symlinked and available* (`.agents/skills/`) for ad-hoc dev-time use; they are simply not load-bearing in the apparatus's standing loop.

**Reversibility.** High. This is a documentation/disposition decision — it changes no code and no run state. Reverse it by deleting this entry and letting harvest re-flag; or adopt any one skill literally by wiring it into the loop. No data migration.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>

---
