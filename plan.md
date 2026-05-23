# Agent System — Improvement Plan

This plan governs the framework's own development. The framework is **executed as
a plan-driven project using its own skills** — `resume-state` → `harvest` →
`gate-check` → execute → `validate` → `run-log`. Improving the framework is
therefore also the framework's largest continuous test of its own Layer-A
discipline.

- **This plan** — `plan.md` — is authoritative. It is **re-sorted every session**
  from the feedback ledger.
- **State file** — `run_state/framework.state.json` — authoritative on resume.
- **Run log** — `run_state/framework.run.jsonl` — append-only, one entry per task.
- **Feedback ledger** — `memory/feedback.jsonl` — append-only, harvested from the
  lead consumer `a_bgt_rsi`.

Created 2026-05-21. Plan version 1.

---

## Charter — the framework's falsifiable claim

The framework demanded a hypothesis, a baseline, a metric, and a decision rule of
every project it touches, while having none for itself. That stops here.

**Mission.** A portable framework that makes agentic development — and
autonomously spawned agents — more disciplined, auditable, and reliable, in *any*
system. `a_bgt_rsi` is the lead consumer that informs it; it is not the only
intended consumer.

**Two claims, two tests — they are different and need different consumers:**

| Claim | What it asserts | Tested by |
|---|---|---|
| **Fidelity** | Each Layer-A skill is an accurate, complete, low-friction description of disciplined practice. | `a_bgt_rsi` — already maximally disciplined, so it can confirm *accuracy*, not *uplift*. |
| **Uplift** | A consumer that adopts the runtime-safe core produces a complete audit trail it would not produce without the framework. | A second, *less* disciplined consumer (Phase 4). `a_bgt_rsi` structurally cannot test this. |

**Metrics.**
- **Conformance** — per skill, `Confirmed` vs `(Diverged + Friction)` findings over
  the last 2 harvests.
- **Open gaps** — count of `gap` findings not yet turned into a skill or section.
- **Audit completeness** (uplift) — on the second consumer, share of fallbacks
  logged / gates honored / validations not coerced, measured with vs. without the
  framework.

**Decision rules** (written before the work, per `plan-research`):
- A skill is **hardened** when 2 consecutive harvests yield no new `Diverged` or
  `Friction` finding against it.
- **v1.0 ships** when: every Layer-A skill is hardened **and** open gaps = 0
  **and** portability is verified on Pi **and** the uplift test passes on a
  second consumer.

---

## How a session runs (the dogfood loop)

1. **`resume-state`** — read this plan + `framework.state.json`; find the resume
   session and the first incomplete task.
2. **`harvest`** — read `a_bgt_rsi`'s activity since the stored watermark; append
   findings to `memory/feedback.jsonl`; advance the watermark. *(From Session 2.)*
3. **Re-sort the backlog** — re-prioritize from `feedback.jsonl`. New `friction`/
   `gap` findings can pre-empt the planned session order.
4. **`gate-check`** — before any gated or irreversible task.
5. **Execute** the session's tasks.
6. **`validate`** — each task's pass-signal as an independent check; never coerce.
7. **`run-log`** — append one entry per task to `framework.run.jsonl`.
8. **`context-save`** — refresh `memory/session-latest.md`; durable decisions to
   `memory/DECISIONS.md`.

---

## The feedback loop (`a_bgt_rsi` → framework)

`a_bgt_rsi` already emits a complete behavioral trace — `run_state/week1.run.jsonl`,
`DECISIONS.md` (D-001…), git history. The framework **reads it; it does not modify
`a_bgt_rsi`** (that project is contract-governed; changing it needs its own gates).

Each harvest reads everything new since the watermark and classifies it **per
skill**:

| Class | Meaning | Becomes |
|---|---|---|
| `Confirmed` | `a_bgt_rsi`'s behavior matched the skill's prescription. | Evidence the skill is accurate — keep. |
| `Diverged` | `a_bgt_rsi` did it differently or contrary to the skill. | Investigate: the skill is wrong, or the project is. |
| `Gap` | `a_bgt_rsi` needed discipline no skill covers. | New-skill / new-section candidate. |
| `Friction` | Invoking the skill *as written* would have been awkward or redundant. | Skill edit candidate. |

**Watermark** lives in `framework.state.json`:
`{ "a_bgt_rsi": { "run_jsonl_lines": N, "last_commit": "<sha>", "last_decision": "D-0NN" } }`.

**Feedback entry shape** (`memory/feedback.jsonl`, append-only):
```json
{"harvest_id":"H001","date":"<ISO>","source":"a_bgt_rsi","skill":"validate",
 "class":"confirmed","evidence":"run.jsonl task_id=day4_end_of_day_artifacts: status=partial_pass with finding field, threshold not coerced",
 "plan_candidate":null}
```

Every `Diverged`/`Gap`/`Friction` finding becomes a backlog item. The backlog is
the input to step 3 of every session.

---

## Target structure — three layers

The 16 skills are one flat list today; they have three different levels of
generality. The plan separates them (Phase 2) without breaking symlinks — via
`layer` and `runtime-safe` frontmatter, not directory renames.

| Layer | Skills | Role |
|---|---|---|
| **A — Core discipline** | `resume-state`, `gate-check`, `validate`, `run-log`, `fallback` | Domain-agnostic. The product. |
| **B — Research vertical** | `plan-research`, `experiment`, `auto-experiment`, `repro-check`, `investigate`, `code-review`, `ship`, `health` | One optional vertical pack among future ones. |
| **C — Orchestration & meta** | `orchestrate`, `harvest`, agent profiles, `context-save/restore` | Infrastructure. |

**Runtime-safe core** = the subset of Layer A that may be embedded in a spawned
or runtime agent: `gate-check`, `validate`, `run-log`, `fallback`, `resume-state`
— rewritten (Phase 5) to assume no human in the loop and no dev harness.

---

## Sessions

Phases 0–2 (Sessions 1–6) are **fixed** — they stand up the loop and resolve the
framework's identity. Sessions 7+ are **feedback-driven**: order and count flex
with the harvest. A minimum-viable arc completes at Session 6; the full arc at 20.

### Phase 0 — Stabilize & bootstrap

**Session 1 — Stop the bleeding; scaffold the dogfood harness.** ✅ *Done 2026-05-21.*
- 1.1 Resolve the boundary leak. `install.sh --global` symlinked all 16 skills
  into `~/.pi/agent/skills/`; `a_bgt_rsi`'s Day-6 Pi runtime would inherit them.
  Remove the Pi-global symlinks and make `install.sh` Pi-global opt-in. *(Gate:
  changes install behavior — human nod. Reversible.)*
- 1.2 Fix concrete doc errors: refresh `memory/projects.md` to `a_bgt_rsi`'s real
  state (Day 4 done / Day 5 in progress, `tests/` populated); correct "13 skills"
  → "16" in `BOUNDARY.md` and `AGENTS.md`; append a `DECISIONS.md` entry
  correcting the "autoresearch" misnomer (the consumer is `a_bgt_rsi`).
- 1.3 Scaffold the harness: create `run_state/framework.state.json`,
  `run_state/framework.run.jsonl`, `memory/feedback.jsonl`.
- 1.4 Append a `DECISIONS.md` entry ratifying this plan: agnostic re-scope,
  dogfooded execution, runtime-safe core.
- **Pass-signal:** `BOUNDARY.md` verification shows no Pi-global leak; `grep "13"`
  finds no stale count; state file, run log, and feedback ledger exist and parse.

### Phase 1 — Build the feedback loop

**Session 2 — Build the `harvest` skill.** ✅ *Done 2026-05-21.*
- 2.1 Author `.agents/skills/harvest/SKILL.md`: read a consumer's run log + git +
  decisions since a watermark, classify per skill, append to `feedback.jsonl`,
  advance the watermark. Written generally (any consumer), with `a_bgt_rsi` as the
  worked example.
- 2.2 Dry-run `harvest` over a small slice of `a_bgt_rsi` history.
- **Pass-signal:** `harvest` produces well-formed `feedback.jsonl` entries; the
  watermark advances; a re-run from the new watermark is idempotent (no dupes).

**Session 3 — First full harvest; baseline conformance report.** ✅ *Done 2026-05-21.*
- 3.1 Run `harvest` over all `a_bgt_rsi` history (preflight → current day).
- 3.2 Produce the baseline conformance report: per skill, `Confirmed` /
  `Diverged` / `Gap` / `Friction` counts.
- 3.3 Seed the backlog (below) from the findings.
- **Pass-signal:** every skill has a baseline classification; the report
  distinguishes fidelity-confirmed skills from those with open findings.

### Phase 2 — Resolve identity & structure

**Session 4 — Re-layer the skills.** ✅ *Done 2026-05-21.*
- 4.1 Add `layer: A|B|C` and `runtime-safe: true|false` frontmatter to every
  `SKILL.md`. No directory renames (symlinks must survive).
- 4.2 Rewrite `AGENTS.md` to present the three layers and the runtime-safe core.
- **Pass-signal:** every skill carries both fields; `AGENTS.md` layer tables match
  the frontmatter exactly.

**Session 5 — Rewrite `BOUNDARY.md` as a layering rule.** ✅ *Done 2026-05-21.*
- 5.1 Replace the blanket "dev-time only" ban with: dev-only skills (Layers B/C)
  vs. runtime-safe core (the 5 Layer-A skills). Define what `runtime-safe`
  *requires* of a skill — no assumed human, no PR/harness calls, minimal context
  cost.
- 5.2 Append a `DECISIONS.md` entry; this supersedes the 2026-05-18 scope-boundary
  decision. *(Gate: reverses a standing rule — explicit ratification required.)*
- **Pass-signal:** `BOUNDARY.md` defines both classes and the `runtime-safe`
  contract; the leak-verification section still holds for Layers B/C.

**Session 6 — Decouple `a_bgt_rsi`-isms from the core.** ✅ *Done 2026-05-21.*
- 6.1 Move project-specific names (Gemma 4 / OpenClaw / NemoClaw / DGX Spark /
  "Day 6") out of `AGENTS.md` and `BOUNDARY.md` into `memory/projects.md`.
- 6.2 Make core-doc examples project-neutral.
- **Pass-signal:** `grep` of core docs for `a_bgt_rsi`-specific terms returns only
  `projects.md` and the `harvest` worked example.

### Phase 3 — Skill hardening, feedback-driven (Sessions 7–12, elastic)

Each session: `harvest` the latest `a_bgt_rsi` activity → pick the highest-priority
open finding from `feedback.jsonl` → improve that skill → re-validate. **The
specific skill per session is chosen at session start, not pre-assigned here.**
Known candidates already on the backlog: `orchestrate` (worktree / file-boundary
protocol), `ship` (no-unified-runner assumption), `health` (stale test
assumption), and runtime-safe rewrites of the Layer-A core.

- **Pass-signal (per session):** the chosen skill's `Diverged`/`Friction` findings
  are resolved — skill edited, or the finding marked a deliberate non-change with
  a reason — and a re-harvest shows no regression.
- **Sessions done:** S7 ✅ — `orchestrate` parallel-worktree protocol (2026-05-22).
  S8 ✅ — `decision-log` skill created (2026-05-22).
  S9 ✅ — `validate` mis-specified-criterion protocol + `partial_pass` (2026-05-22).
  S10 ✅ — `run-log` status enum expanded and defined (2026-05-23).
  S11 ✅ — `ship` integration flow + no-unified-runner; `health` light touch (2026-05-23).
  S12 ✅ — `gate-check` attestation- vs verification-cleared gates (2026-05-23).

### Phase 4 — Portability & uplift

**Session 13 — Pi migration check** (the long-deferred Task 5). Verify the
framework loads and runs in Pi; verify the runtime-safe core can be loaded into a
Pi runtime agent without the dev-only layers.

**Session 14 — Install/discovery abstraction.** Generalize `install.sh` beyond
hardcoded `~/.claude` and `~/.pi` toward a discovery story for "any system."

**Sessions 15–16 — Onboard a second, weaker consumer** *(Gate: human picks the
consumer — toy or real)*. Run it with and without the runtime-safe core; measure
audit completeness. This is the **uplift test** `a_bgt_rsi` cannot provide.

### Phase 5 — Autonomy & generalization

**Sessions 17–18 — Make "autonomously spawned agents" first-class.** A spawned
agent receives a task contract, the runtime-safe core, a self-gating protocol, a
self-reporting protocol, and an explicit authority boundary. Likely a new
`spawn-contract` template skill.

**Session 19 — Package Layer B as an optional vertical pack** and document how to
add other verticals (product, data-pipeline, …).

**Session 20 — v1.0.** Rewrite `README.md`/`AGENTS.md` for "any system"; final
harvest; retrospective; check the Charter's decision rule against accumulated
evidence.

---

## Backlog (re-sorted every session from `feedback.jsonl`)

Re-sorted **Session 3** from harvests H001–H002 — 25 findings, see
`memory/conformance.md`. Priority: gaps, then friction, then structural. Each
item cites the harvest finding(s) behind it.

**P1 — gaps (a skill is missing or silent)**
- ✅ **addressed S7** — `orchestrate` gained a parallel-worktree execution
  protocol (file-boundary allow-lists, mock isolation, pre-merge boundary
  verification, `--no-ff` merges, completion sentinels). Re-harvest pending to
  confirm and mark hardened. *(H002 orchestrate/gap)*
- ✅ **addressed S8** — created the `decision-log` skill (mandatory
  Alternatives + Reversibility + supersedes-chains); the framework's
  `DECISIONS.md` template updated to match. *(H002 decision-log/gap)*
- No skill for autonomously spawned agents — task contract, self-gating,
  self-reporting, authority boundary. *(Phase 5; 2026-05-21 analysis)*

**P2 — friction (a skill exists but mis-fits real use)**
- ✅ **addressed S9** — `validate` gained a "When the criterion itself is
  wrong" protocol (verify intent separately, report the criterion as
  mis-specified, escalate, never coerce). *(H002 validate/friction)*
- ✅ **addressed S9 (validate) + S10 (run-log)** — `validate` gained a
  tightly-scoped `partial_pass` overall verdict; `run-log`'s status enum
  gained `partial_pass` (with `started` and `escalated`). *(H002 validate/friction)*
- ✅ **addressed S10** — `run-log`'s status enum expanded to `started` /
  `passed` / `partial_pass` / `failed` / `aborted` / `halted` / `escalated` /
  `skipped`, each defined; enum declared a default a project may extend.
  *(H001 + H002 + H003)*
- ✅ **addressed S11** — `ship` step 5 generalized into "Integrate" with three
  named flows (PR-based, commit-to-main, worktree-merge); Rules use
  "integration message" not "PR". *(H002 ship/friction)*
- ✅ **addressed S11** — `ship` step 2 + `health` step 1 handle projects with
  no unified runner — an enumerated per-unit test set is "the suite".
  *(H002 ship/friction)*
- ✅ **addressed S12** — `gate-check` now defines two clearance modes
  (attestation-cleared, verification-cleared) and refines the "never silently
  clear" rule. *(H001 gate-check/friction)*
- `fallback` does not address a fallback *selection* that is itself gated.
  *(H002 fallback/friction)*
- `experiment` mandates a separate `experiments.md`; allow the run log to be
  the ledger. *(H002 experiment/friction)*
- `repro-check` has no check that a run was not silently mocked/stubbed — a
  stray `MOCK_LLM` flag faked a result in `a_bgt_rsi`. *(H003 repro-check/friction)*

**P3 — structural**
- `memory/` does three jobs (framework-self memory, cross-project registry,
  consumer templates) with no separation. *(2026-05-21 analysis)*

**Untested by `a_bgt_rsi`** — need a different consumer (Phase 4 uplift test):
`plan-research`, `health`, `auto-experiment`, `context-save`, `context-restore`.

---

## Gates

| Where | Gate | Cleared by |
|---|---|---|
| Session 1.1 | Install-behavior change | Human nod (low stakes, reversible). |
| Session 5.2 | Rewriting the standing dev-time-only rule | Explicit ratification + `DECISIONS.md` entry. |
| Sessions 15–16 | Choice of the second consumer | Human selects the project. |

---

## Living-plan note

This plan is a record, not reality. Each session reconciles it against the repo
and against `feedback.jsonl`. When the harvest disagrees with the planned order,
the harvest wins — surface the divergence, re-sort, and log it. The 5–20 session
range is honored: Sessions 1–6 are the minimum viable arc (loop running, identity
resolved); Sessions 7–20 are the feedback-driven remainder.
