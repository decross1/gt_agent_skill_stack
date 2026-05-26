# Decisions Log

Append-only, date-stamped record of decisions and corrections. **Never rewrite or
delete entries** — add new ones. Newest at the bottom. Each entry follows the
decision-log skill: decision, alternatives, rationale, reversibility, supersedes.

Format:

```
## YYYY-MM-DD — <short title>
**Decision:** ...
**Alternatives:** ...
**Rationale:** ...
**Reversibility:** trivial | easy | medium | hard — <cost of undoing>
**Supersedes:** <date/title, or "none">
```

---

## 2026-05-18 — Agent system scaffolded
**Decision:** Created a portable agent framework (skills + file memory) authored
to the Agent Skills standard, runnable in both Pi and Claude Code via symlinks.
Adopted a curated, research-tuned subset of gstack rather than the full
product-oriented framework.
**Why:** Target harness is Pi; current harness is Claude Code; the project
(`autoresearch`) is an ML/research pipeline with no product-UI dimension, so
gstack's CEO/design/QA-browser roles do not apply.
**Supersedes:** none

## 2026-05-18 — Added execution-discipline skills
**Decision:** Added 4 skills — `gate-check`, `validate`, `run-log`,
`resume-state` — and adapted `experiment` (autonomous loop section) and
`plan-research` (design-vs-execute pointer).
**Why:** Explored the primary consumer `/home/decross1/projects/a_bgt_rsi` — a
contract-governed, plan-driven research program (authoritative `plan.yaml`,
state-file resume, blocking human gates, JSONL run log, validations never
coerced). The original gstack-derived skills were a design/ship loop and did
not cover plan-execution discipline, which is this project's core need. The
gstack safety roles (`/careful`/`/freeze`/`/guard`) dropped on 2026-05-18 are,
reframed, exactly this gap. Skills stay general-purpose.
**Supersedes:** partially revises the 2026-05-18 scaffold decision's skill set.

## 2026-05-18 — Scope boundary: dev-time vs project-runtime
**Decision:** Established that this framework is a dev-time harness only; its
skills must not be loaded into any project's runtime agent. Added `BOUNDARY.md`
and a `## Scope boundary` section to `AGENTS.md` / `README.md`.
**Why:** Explored `a_bgt_rsi`'s architecture — its runtime orchestrator (Gemma 4
+ OpenClaw + NemoClaw) also runs on Pi. With the dev skills installed globally
in `~/.pi/agent/skills/`, the apparatus runtime could inherit them. The two
"orchestrators" (dev-time and apparatus-runtime) must stay separate.
**Supersedes:** none

## 2026-05-21 — Correction: the lead consumer is `a_bgt_rsi`, not `autoresearch`
**Decision:** The 2026-05-18 "Agent system scaffolded" entry names the consumer
project `autoresearch`. That is incorrect: `autoresearch` is a third-party repo
cloned *inside* `a_bgt_rsi` (`a_bgt_rsi/clones/autoresearch`). The framework's
lead consumer is `/home/decross1/projects/a_bgt_rsi`.
**Why:** This log is append-only; the original entry cannot be rewritten. This
entry corrects the record.
**Supersedes:** corrects — does not supersede — the project name in the
2026-05-18 "Agent system scaffolded" entry.

## 2026-05-21 — Framework re-scoped: agnostic, self-hosted, runtime-safe core
**Decision:** The framework is re-scoped from an ML/research-tuned toolkit to an
*agnostic* framework for disciplined agentic development and autonomously spawned
agents, usable by any system. `a_bgt_rsi` remains the lead consumer that informs
it. Three structural commitments, ratified in `plan.md` (v1):
1. **Dogfooded** — the framework's own development runs as a plan-driven project
   using its own skills (`plan.md` + `run_state/framework.state.json` +
   `run_state/framework.run.jsonl`).
2. **Read-only feedback** — a `harvest` skill scores each skill against
   `a_bgt_rsi`'s execution trace into `memory/feedback.jsonl`; `a_bgt_rsi` itself
   is never modified.
3. **Runtime-safe core** — a subset of Layer-A skills will become embeddable in
   spawned/runtime agents; `BOUNDARY.md`'s blanket dev-time-only ban becomes a
   layering rule (scheduled for Session 5).
**Why:** The framework was a high-fidelity mirror of one project's discipline but
had no falsifiable claim about its own value, no feedback loop, and a
"research-tuned" identity that contradicted the goal of general use. `plan.md`
gives it a charter, metrics, decision rules, and a 20-session improvement arc.
**Supersedes:** revises the scope of the 2026-05-18 "Agent system scaffolded"
decision. The 2026-05-18 "Scope boundary" decision stands until Session 5
formally rewrites `BOUNDARY.md`.

## 2026-05-21 — BOUNDARY.md rewritten as a layering rule; runtime-safe core established
**Decision:** `BOUNDARY.md`'s blanket "all skills are dev-time only" rule is
replaced by a two-class layering rule: **dev-only skills** (Layers B and C) that
must never enter a project's runtime agent, and a **runtime-safe core** (the 5
Layer-A skills — `resume-state`, `gate-check`, `validate`, `run-log`,
`fallback`) that may be *deliberately* embedded in a spawned / runtime agent.
`BOUNDARY.md` now defines the `runtime-safe` contract: no assumed human, no
dev-harness dependency, minimal context cost, no surprising side effects, a
closed dependency set. Per-skill conformance to that contract is verified in
Phase 3.
**Why:** The framework's goal (2026-05-21 re-scope) is to serve autonomously
spawned agents in any system, not only dev-time sessions. A blanket ban made the
framework's most general, most valuable asset — the execution-discipline core —
unusable where it is most needed. The dev-time/runtime line did not move; it
sharpened from "all skills" to "the dev-only layers."
**Supersedes:** the blanket rule of the 2026-05-18 "Scope boundary: dev-time vs
project-runtime" decision. The dev-time/runtime *distinction* that decision drew
still stands.
**Gate:** this decision reverses a standing rule; ratified by explicit human
go-ahead, 2026-05-21.

## 2026-05-24 — Treat 100% metrics in small-N tests as suspicious-clean
**Decision:** When a research metric reads exactly 100% (or 0%) on a small-N
test driven by a strongly-directive prompt, do not treat the result as
evidence of robustness. Investigate the prompt and the N before adopting.
**Correction:** Default to disbelieving small-N clean reads; raise N or
soften the prompt before trusting.
**Alternatives:** (a) trust the metric and ship — rejected, this is how
prior-driven results get over-claimed (cf. D-028 cooperation lock-in is a
Gemma 4 prior); (b) widen the test set silently — rejected, hides the
methodological constraint.
**Rationale:** Day-4 tool_call_invocation_rate=1.00 on the e2e set (see
brain page `anomaly-tool-call-100pct`) was driven by a system prompt
mandating tool use. A 100% metric on a small N with a strong directive
prompt is structurally biased upward, not a robustness signal.
**Reversibility:** trivial — single-line rule of practice, no infra
implication.
**Supersedes:** none

## 2026-05-24 — Reconcile state-file lag against run-log during gate-armed periods
**Decision:** When `resume-state` finds the state file's
`completed_tasks` shorter than the run log's completed entries across a
gate-armed window, treat the run log as canonical for the held period.
Walk it to determine what is done; do not re-run completed work based on
the lagging state.
**Correction:** Trust the run log over the state file when they disagree
across a gate-armed period.
**Alternatives:** (a) require write-through to state during holds —
rejected, makes the "held but working" state ambiguous (state in a hold
should be a record of the hold, not a mutable buffer); (b) leave the
behavior project-specific — rejected, leaves a real resume-during-hold
recovery failure mode unguarded across projects.
**Rationale:** H006 finding in `a_bgt_rsi` `week1.run.jsonl` L137 — 16
day_7 task IDs were backfilled into `state.completed_tasks` AFTER the
publication-review gate cleared at L136. During the gate-armed window
(L125 onward), the run log had the tasks; the state file did not. A
session that crashed and resumed during the hold would have either
re-run completed work (trusting state) or invented an ad-hoc
reconciliation; making the run log canonical for held periods is what
the consumer did manually and is the rule we encode now.
**Reversibility:** trivial — single-paragraph protocol clarification in
`resume-state` SKILL.md; the rule of practice itself is the durable
artifact, regenerated into `rules.md` as FR-002 by `regen_rules.py`.
**Supersedes:** none — extends [[resume-state]] step 5.

## 2026-05-24 — Defer S19-S20 uplift test pending consumer choice
**Decision:** Defer the Phase-4 uplift test (S19-S20: onboard a second,
less-disciplined consumer, run it with and without the runtime-safe core,
measure audit-completeness uplift). No consumer is being chosen at this
time; the gate `s19_choose_uplift_consumer` clears as
*deferred-by-human-choice*. Advance to S21 (Phase 5).
**Alternatives considered:**
(a) Spin up a toy `latency-probe` project — rejected for now: no immediate
    appetite, and a toy's realism is bounded.
(b) Spin up a toy RAG eval harness — rejected for now: same reasoning.
(c) Adopt an existing real project — rejected for now: no named candidate;
    higher scope risk than a toy without proportional payoff today.
(d) Proceed to Phase 5 (S21+) — **chosen.**
**Rationale:** The Charter's uplift claim is structurally testable only
with a less-disciplined second consumer; doing it well requires
deliberate setup that the user is not ready to commit to today. Phase 5
(autonomous spawned agents) does not depend on uplift evidence being
gathered first. The deferral is recorded so v1.0 (S24) can be honest
that uplift remains untested — or so a future session can pick it up.
**Reversibility:** trivial — return to S19 when a consumer is named;
all S19-S20 plan content remains in `plan.md`.
**Supersedes:** none.
