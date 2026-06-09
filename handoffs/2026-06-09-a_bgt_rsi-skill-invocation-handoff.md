# Handoff: a_bgt_rsi skill-invocation & brain-alignment remediation

**Date:** 2026-06-09
**For:** the a_bgt_rsi primary (main) planning session
**Source:** a 2026-06-09 adversarially-verified skill/brain alignment review of the
`a_bgt_rsi` consumer project, run from the `agent_system` framework session.
**28 of 31 findings held** under an independent adversarial verifier; every claim
below was ground-truthed by reading the named files on disk, and the verifier's
precise corrections have been applied to the values stated here.

## What this is

A planning-ready briefing on where the framework's skills are *referenced but not
run* inside `a_bgt_rsi`, and which of those gaps now matter. The framing, plainly:

- The framework's skills are **referenced-not-run** in the consumer — largely **by
  governed design** (Dynamic Workflows + a verification gate substitute for several
  skills on purpose), not by neglect.
- The **BOUNDARY firewall is intact**: no dev-time skill is loaded into the
  gemma/Nara runtime, and the runtime **emits into the brain but never reads it**.
- The gaps below matter **now** because **D-037 Dynamic Workflows** and **D-040
  unattended "Nara" autonomy (effective at beta)** mean autonomous agents spawn
  soon — and the discipline that should govern them is currently prose-only.

Nothing in this handoff injects any dev skill into the runtime. Each item that
edits an inviolate consumer rule carries a **HUMAN ATTESTATION** block; the file
edits themselves are deferred to a human-attested apply step.

## Priority order

| # | Priority | Item | Touches | Attestation |
|---|---|---|---|---|
| 1 | **P0** | spawn-contract ledger — materialize `run_state/spawn.jsonl`, emit per build agent | consumer `CLAUDE.md` rules 3–5 (inviolate) | **Required** |
| 2 | **P0** | run-log attribution — add `agent` to inviolate rule 6; per-build-agent rows | consumer `CLAUDE.md` rule 6 (inviolate) + runtime writer | **Required** |
| 3 | P1 | merge-gate disambiguation — name the framework `code-review` skill | consumer `CLAUDE.md` line 64 (inviolate) | **Required** |
| 4 | P1 | narrate required (propose conditional) as a post-task step | consumer `CLAUDE.md` discipline rule 5 | **Required** |
| 5 | P1 | brain-recall on the dev-time build-agent path (runtime-excluded) | consumer `CLAUDE.md` discipline rule 3 | **Required** |
| 6 | P2 | referenced-only record — declare governed substitution on the record | consumer `DECISIONS.md` (append-only note) | **Required** |

Items 3–6 share one location (`CLAUDE.md` §"Dynamic Workflow discipline") and one
dependency: item 5 needs a real build-agent spawn-contract to attach to, so it
must land **after** item 1 materializes the ledger.

---

## P0 — Wire spawn-contract emission into the consumer Dynamic-Workflow runner

### 1. Problem + evidence

Consumer `CLAUDE.md` rule 3 (`/home/decross1/projects/a_bgt_rsi/CLAUDE.md:59-66`,
"Spawn-contract per build agent") and `DECISIONS.md` D-037 (`:1900`, guardrail
"spawn-contract per build agent") both *require* a spawn contract for every build
agent a Dynamic Workflow fans out. **The requirement is prose-only — nothing
writes a spawn ledger.**

Verified, by reading the real files:

- **No spawn ledger exists anywhere in the consumer.** `find /home/decross1/projects/a_bgt_rsi -name spawn.jsonl`
  returns nothing. A repo-wide grep for `spawn_id` / `spawn.jsonl` over `*.py`
  finds **zero code** — those identifiers appear nowhere in the consumer. The only
  consumer mentions of `spawn-contract` are **prose** (`CLAUDE.md`, `DECISIONS.md`
  D-037, `docs/specs/gamma_permission_scoped_subagents.md`, `human/sessions/2026-06-05.md`).
  The only `spawn.jsonl` on disk is the framework's own
  `/home/decross1/projects/agent_system/run_state/spawn.jsonl`, which holds **4
  stale entries** — SP-001 and SP-002, both timestamped `2026-05-25` (2 spawn_ids ×
  2 status lines), none from the consumer.
- **Live fan-out ran with no contract.** The 2026-06-08 session note
  (`human/sessions/2026-06-08.md:30`) records "Slice α — coordinator brain (Dynamic
  Workflow `wf_47ff851f-5d1`, **6 agents**) — DONE", and `:65` records pre-commit
  review `wf_744e0f6d-f04` (**26 agents**); the 2026-06-09 beta-hardening day opens
  at run-log row `derisk_harden_beta_workflow_start` (`2026-06-09T03:12:47`). The
  current beta-hardening fan-out is **6 agents — but only 2 of them are build
  agents**: per run-log row 1003, **A1–A4 are assess agents (read-only
  audit/design)** and only **B1–B2 are build agents** that create disjoint NEW
  files. For none of these runs does any `spawn_id` record exist.
- The two 2026-06-09 run-log rows carry only the bare 6-field schema (`task_id,
  status, observable_actual, observable_expected, duration_ms, timestamp`) —
  confirming the primary session writes these JSONL rows by hand, and that D-037
  rule 5 (per-agent start+finish) and rule 3 (the spawn contract) are both unmet at
  the artifact level.

**Scope (firewall-respecting).** These are **dev-time agents in the primary Claude
Code session** (the native Opus 4.8 `Workflow` primitive — D-037), so `CLAUDE.md`
rule 3 genuinely applies. spawn-contract governs **all 6 as autonomous children**;
the file-creation authority cap applies only to the 2 build agents. This is **not**
the gemma/Nara runtime: `orchestrator/runtime.py` (`PyRuntime`/`NemoClawRuntime`)
and `orchestrator/subagent.py` are the apparatus RUNTIME substrate, which per
`BOUNDARY.md` §"The brain firewall" EMITS into the brain but never reads it, and
into which dev skills must never load. **This handoff proposes no skill embedding
into any gemma worker.** spawn-contract is `runtime-safe: true`, but here it is used
purely as the *parent's dev-time discipline* over the workflow it launches.

### 2. The design

**What.** Make the spawn ledger a real, append-only artifact at
`run_state/spawn.jsonl` in the consumer, written per spawned agent, exactly as the
`spawn-contract` skill prescribes
(`/home/decross1/projects/agent_system/.agents/skills/spawn-contract/SKILL.md:43-78`
— "append events to the project's spawn ledger (default: `run_state/spawn.jsonl`)
... the initial spawn event holds the full contract; subsequent events update
`status`").

**Where the hook is.** The fan-out is the native `Workflow` primitive driven from
the **primary session**, not a Python `dispatch()` function — so the hook is a
**discipline step bound to the workflow launch/reconcile boundary**, codified where
that boundary already lives:

- **Emit-before-launch hook:** `CLAUDE.md:59-66` (Dynamic Workflow discipline **rule
  3**). Tighten rule 3 from "spawn-contract per build agent (the skill): exact files
  ... done-condition ... report format" to additionally require: *each spawned
  agent's contract is appended to `run_state/spawn.jsonl` with `status:"spawned"`
  BEFORE the Workflow agent is launched; an unwritten contract is a fail-to-launch.*
  This is the skill's Rule "Contract before launch" (`SKILL.md:114`) made mechanical
  at the one place the consumer already gates fan-out.
- **Reconcile-after hook:** `CLAUDE.md:67-68` (discipline **rule 5**, "Workflow
  run-logging ... Phase/agent start+finish") and **rule 4** (`:63-66`, the single
  serial integrator + verification gate). The serial integrator — the only authority
  that touches `run_state/` per rule 2 (`:49-58`) — appends the closing `{status:
  completed|escalated, result:{...}}` line per `spawn_id` at fan-in, when it runs
  `code-review` + suite + the one `env -u MOCK_LLM` smoke (rule 4). This co-locates
  spawn reconciliation with the existing run-log start+finish entries the integrator
  already writes.

**Ledger placement note (verified).** Consumer `.gitignore:64-71` already ignores
every `run_state/*.jsonl` operational log (incl. `week1.run.jsonl`). `run_state/spawn.jsonl`
therefore lives as a **local working-tree artifact**, not a committed file —
identical to how the run log behaves today, and matching the skill's default. The
beta gate (below) inspects the live working-tree file, not a commit.

**The per-agent record (each fanned-out agent appends BEFORE launch).** A build
agent (B1–B2) carries the disjoint-new-files authority cap; an assess agent
(A1–A4) carries a read-only cap:

```json
{
  "timestamp": "<ISO 8601, spawn time>",
  "spawn_id": "SP-<wf_id>-B1",
  "parent_workflow_id": "wf_47ff851f-5d1",
  "parent_task_id": "<integrator run-log task_id that opened the workflow>",
  "child_task_id": "B1",
  "status": "spawned",
  "contract": {
    "task_statement": "<one paragraph: for B1/B2 the disjoint new files this agent creates; for A1-A4 the read-only audit/design it performs>",
    "done_condition": "<B1/B2: its test green under MOCK_LLM, e.g. 'pytest tests/test_<worker>.py green with MOCK_LLM=1'; A1-A4: its audit/design artifact delivered>",
    "skill_subset": ["resume-state","gate-check","validate","run-log","fallback"],
    "authority_cap": "BUILD (B1-B2): disjoint NEW files only (its worker + its test); NEVER spine (orchestrator/nara.py, tool_registry.py, schema/iteration_record.schema.json), run_state/, or ui/.  ASSESS (A1-A4): READ-ONLY — audit/design only; writes NO source files.",
    "self_gating_rules": "halt and escalate on any spine/run_state/ui write attempt, on a failing done-condition, or on budget exhaustion",
    "reporting_format": "report-back summary + done_condition_check (pass|fail|inconclusive), returned to the serial integrator; no commit",
    "escalation_path": "serial integrator (the single commit authority) at fan-in",
    "budget": {"wall_time_seconds": 600, "iterations": null, "cost_usd": null},
    "state_basis": "working-tree@<parent-sha>"
  }
}
```

**The closing record (serial integrator appends per `spawn_id` AFTER, at the verify
gate):**

```json
{
  "timestamp": "<ISO 8601>",
  "spawn_id": "SP-<wf_id>-B1",
  "status": "completed",
  "result": {
    "child_summary": "<the agent's report-back>",
    "done_condition_check": "pass|fail|inconclusive",
    "verified_at": "<ISO 8601>",
    "verified_by": "<integrator run-log task_id that ran reconciliation>"
  }
}
```

`status:"completed"` only when the done-condition validates pass (`SKILL.md:126`
"Validate the done-condition"); otherwise `escalated`. The record uses the schema's
required field names exactly (`SKILL.md:53-78`), including `self_gating_rules`,
`reporting_format`, and `escalation_path`; `parent_workflow_id` is added
(consumer-specific) since the parent here is a `wf_*` Workflow, not a single parent
task. The build-agent `authority_cap` is the verbatim "disjoint NEW files / no
spine" rule already in `CLAUDE.md:49-58` (rule 2), so the ledger encodes the
existing boundary rather than inventing a new one.

**Why a ledger and not just more run-log rows.** The run log answers "what step
ran"; the spawn ledger answers "under what bounded contract was each autonomous
child *authorized to run, and was that boundary honored*" — the exact account D-037
rule 3 demands and the "wrote to main checkout / forked from stale HEAD" failure
modes (`CLAUDE.md:62`) need to be auditable against. It is the same append-only,
latest-status-per-id model as the run log, so it adds no new machinery.

#### 🔒 HUMAN ATTESTATION REQUIRED

This change tightens the consumer's own inviolate operating contract (`CLAUDE.md`
Dynamic Workflow discipline rules 3–5) and how the live beta-hardening workflow
runs. A human must attest before it lands.

- **VALUE.** Every autonomously fanned-out agent (2 build agents B1–B2 + 4 assess
  agents A1–A4 today; the 6-, 7-, and 26-agent workflows already run) gets a
  durable, append-only contract recording its task, its done-condition, its
  authority cap, and whether the boundary held. "6 agents fanned out, zero record of
  what any was authorized to do" stops being possible. The bounded-child failure
  modes D-037 names — wrote-to-main-checkout, forked-from-stale-HEAD, agent exceeded
  its file scope — become auditable after the fact instead of invisible.
- **REASON.** The requirement already exists and is already being violated on every
  run: `CLAUDE.md:59` and D-037 mandate "spawn-contract per build agent", but the
  artifact has never been written (no `run_state/spawn.jsonl` in the consumer; the
  only one on disk is the framework's 4 stale 2026-05-25 entries). Prose-only
  governance of unattended fan-out is the gap. D-040's unattended-Nara contract
  ships at β and *explicitly rejected* "always-on with no formal contract" — closing
  this loop dev-time, before β, is the prerequisite discipline.
- **PURPOSE.** Convert rule 3 from intention into a mechanical, observed artifact at
  the exact point the primary session already gates fan-out (emit-before-launch at
  the rule-3 boundary, `CLAUDE.md:59`) and fan-in (reconcile-after by the serial
  integrator at the rule-4/5 verify gate, `CLAUDE.md:63-68`) — with no new code path
  and no skill embedded into any gemma runtime worker.
- **PROPOSED BETA GATE.** β does not ship until **one `env -u MOCK_LLM` smoke run of
  a Dynamic Workflow produces a non-empty `run_state/spawn.jsonl`** in the consumer
  — i.e. at least one `{status:"spawned"}` contract line per fanned-out agent BEFORE
  launch, each closed by a matching `{status:"completed"|"escalated"}` line from the
  integrator, with `parent_workflow_id` matching the run's `wf_*` id. An empty or
  absent ledger after a fan-out is a beta blocker. (Inspect the live working-tree
  file; it is git-ignored by design.)

**Data for the main session**

- HOOK (emit-before-launch): `/home/decross1/projects/a_bgt_rsi/CLAUDE.md:59-66` —
  Dynamic Workflow discipline rule 3 ("Spawn-contract per build agent"). Tighten to
  require each fanned-out agent append its contract to `run_state/spawn.jsonl` with
  `status:'spawned'` BEFORE the Workflow agent launches (unwritten contract =
  fail-to-launch).
- HOOK (reconcile-after): `/home/decross1/projects/a_bgt_rsi/CLAUDE.md:67-68` (rule
  5, Workflow run-logging) + `:63-66` (rule 4, serial integrator + code-review +
  suite + `env -u MOCK_LLM` smoke verify gate). The serial integrator — the only
  writer to `run_state/` per rule 2 (`:49-58`) — appends the closing `{status:
  completed|escalated, result}` line per `spawn_id` at fan-in.
- LEDGER PATH: `run_state/spawn.jsonl` (consumer). Matches spawn-contract SKILL
  default (`/home/decross1/projects/agent_system/.agents/skills/spawn-contract/SKILL.md:43`).
  It is a LOCAL working-tree artifact — `.gitignore:64-71` already ignores all
  `run_state/*.jsonl` logs (same as `week1.run.jsonl`); not committed.
- NOT THE RUNTIME: `orchestrator/runtime.py` (`PyRuntime.log_event` @ `:91-98`,
  `NemoClawRuntime` stub) and `orchestrator/subagent.py` are the gemma/Nara RUNTIME
  substrate (firewalled per `BOUNDARY.md`). The fan-out is the native Opus 4.8
  `Workflow` primitive in the PRIMARY dev-time session — there is no Python
  `dispatch()` to patch. No skill is embedded into any gemma worker.
- ROLE LABELS (per run-log row 1003): A1–A4 = **assess agents** (read-only
  audit/design); B1–B2 = **build agents** (create disjoint NEW files). spawn-contract
  governs all 6 as autonomous children; the file-creation `authority_cap` applies
  only to B1–B2, A1–A4 get a read-only cap.
- SPAWN RECORD SCHEMA (per agent, BEFORE launch): `{timestamp, spawn_id:'SP-<wf_id>-<child>',
  parent_workflow_id:'wf_*', parent_task_id, child_task_id, status:'spawned',
  contract:{task_statement, done_condition, skill_subset:[resume-state,gate-check,validate,run-log,fallback],
  authority_cap (build: disjoint NEW files only / never spine/run_state/ui; assess:
  read-only), self_gating_rules, reporting_format, escalation_path,
  budget:{wall_time_seconds:600,iterations:null,cost_usd:null}, state_basis:'working-tree@<parent-sha>'}}`.
- CLOSING RECORD (integrator, AFTER, per spawn_id): `{timestamp, spawn_id,
  status:'completed'|'escalated', result:{child_summary,
  done_condition_check:'pass|fail|inconclusive', verified_at, verified_by}}`.
  `status:'completed'` only when the MOCK_LLM done-condition validates pass.
- EVIDENCE: 0 `spawn.jsonl` in consumer (find returns nothing); 0 `spawn_id`/`spawn.jsonl`
  identifiers in consumer code at all. The only consumer mentions of `spawn-contract`
  are prose (`CLAUDE.md`, `DECISIONS.md` D-037 @ `:1883`/`:1900`,
  `docs/specs/gamma...`, `human/sessions/2026-06-05.md`). Framework
  `run_state/spawn.jsonl` = 4 stale entries SP-001/SP-002 dated 2026-05-25. Live
  fan-outs with no contract: `wf_47ff851f-5d1` (6 agents, `sessions/2026-06-08.md:30`),
  `wf_744e0f6d-f04` (26 agents, `:65`), `wf_0ecc5da4-eae` (7 agents,
  `sessions/2026-06-05.md:31`). 2026-06-09 run-log rows carry only the bare 6-field
  schema.
- BETA GATE: β blocked until one `env -u MOCK_LLM` Dynamic-Workflow smoke yields a
  NON-EMPTY `run_state/spawn.jsonl` — ≥1 `{status:spawned}` per fanned-out agent
  BEFORE launch, each closed by a matching `{status:completed|escalated}` from the
  integrator, `parent_workflow_id` == the run's `wf_*` id. Empty/absent ledger after
  fan-out = beta blocker. Aligns with D-040 (effective at β) rejecting "always-on
  with no formal contract".
- `needs_human_attestation=true`: edits the consumer's inviolate `CLAUDE.md` Dynamic
  Workflow discipline (rules 3–5) and governs the live beta-hardening workflow.

---

## P0 — Reconcile run-log attribution so unattended multi-agent runs are reconstructible

### The problem

The consumer's run log cannot answer "which agent did this?" — and the apparatus is
about to run unattended (D-040 ships Nara autonomy at beta) and already fans out
multiple build agents per workflow. An unattended multi-agent run is therefore
currently **unauditable after the fact**: the log is anonymous-by-task-id, exactly
the failure the framework's brain exists to prevent.

### Evidence (all read from disk, 2026-06-09)

- **Framework already moved.** Commit `2690b5b` (`2026-05-27 00:07:45 +0000`, "S24a:
  run-log schema gains `agent` + `skill_used`; agent and skill projected") added the
  two fields to the canonical entry shape. They are codified as **FR-003** in
  `memory/brain/rules.md:24` ("`agent` (required)… `skill_used` (optional)") and
  written into the skill at `.agents/skills/run-log/SKILL.md:30-44` (default schema
  lines 30-31; the "Name the agent" rule at lines 87-91).
- **Consumer contract still on the old 6-field schema.** `a_bgt_rsi/CLAUDE.md:151-154`
  (inviolate rule 6) mandates exactly:
  `{timestamp, task_id, status, observable_actual, observable_expected,
  duration_ms}` — no `agent`, no `skill_used`.
- **Population is zero.** Over the live `run_state/week1.run.jsonl` (**1004 rows**):
  `agent` present in **0/1004**, `skill_used` present in **0/1004**. The `agent` key
  does not appear in the union of keys across *any* row.
- **Root cause is structural, not just policy.** The writer
  `orchestrator/runtime.py:91-98` (`PyRuntime.log_event`) does `row = {"timestamp":
  _utcnow_iso(), **event}` — it never injects `agent`, and the ~13 call sites in
  `orchestrator/nara.py` (e.g. `:354`, `:384`, `:478`, `:819`) build event dicts
  with only domain keys (`event_type`, `iteration_id`, `topic`, `note`…). So no
  caller supplies `agent` either. Nothing in `runtime.py` / `tool_registry.py`
  writes an `agent` field.
- **The multi-agent gap is already visible in the data.** **12 anonymous
  Dynamic-Workflow rows (all `agent:None`), at `week1.run.jsonl` lines 886–981**
  record workflow execution (task_ids like `loop_v1_build_via_dynamic_workflow`,
  `exp004_combinatorial_auction_via_dynamic_workflow`,
  `next_steps_build_via_dynamic_workflow`). Every one is a single anonymous summary
  line — no per-build-agent `start`+`finish` pair. The **2026-06-05** beta-hardening
  workflow `wf_c4a70caf-a81` that fanned out 6 build agents (A1–A4, B1–B2) left one
  anonymous summary row (`week1.run.jsonl:904`) and **no per-agent rows**. This is
  **D-037 rule 5 unmet** (`a_bgt_rsi/DECISIONS.md:1900`, "workflow phases log to
  `run_state/week1.run.jsonl`") and **CLAUDE.md §"Dynamic Workflow discipline" item
  5** unmet ("Phase/agent start+finish log… as first-class entries").

### Discrepancy found vs. the briefing (must surface)

The briefing states open proposal **`prop-82537922`** "scopes the rule-6 bump." That
id **does not exist** — `grep` for `82537922` across both repos returns no match
(`grep-exit=1`). The proposals ledger `memory/brain/proposals.jsonl` uses `P-NNN`
ids; proposals **P-001..P-007 all exist and are all closed** (open count = 0), and
**none of them scopes rule-6 / the run-log schema** (P-002 is about trusting the
tool_call rate; P-004 is spawn-contract `state_basis`). **There is currently NO
proposal tracking the rule-6 bump.** The action below is therefore **file a new
proposal** (next free id `P-008`) — not close an existing record.

### The change

**(a) Reconcile inviolate rule 6** to require `agent` and accept optional
`skill_used`, aligning the consumer with FR-003 / commit `2690b5b`. New schema:
`{timestamp, task_id, agent, status, observable_actual, observable_expected,
duration_ms, skill_used?}` — `agent` **required**, `skill_used` optional (present
only on skill-phase entries). This is an **inviolate-rule edit → requires human
attestation** (see block below). Existing 1004 rows stay unrewritten (append-only
honored); attribute them at read time by per-file canonicalization, consistent with
FR-003 (`week1.run.jsonl` → `nara`).

**(b) Emit two first-class run.jsonl entries per workflow build agent.** For each
build agent a Dynamic Workflow spawns, write a `started` entry at fan-out and a
terminal entry (`passed`/`failed`/`aborted`) at join, with `agent="workflow:wf_<id>/<role>"`
(e.g. `workflow:wf_c4a70caf/B1`, `workflow:wf_c4a70caf/integrator`). This satisfies
CLAUDE.md Dynamic-Workflow-discipline item 5 and D-037 rule 5. Mechanically: thread
an `agent` field through `PyRuntime.log_event` (`orchestrator/runtime.py:91`) —
either as an explicit param defaulting to the run's identity, or by requiring
callers to include `agent` in the event dict and asserting its presence — and have
the workflow harness stamp the per-role value on the two bracketing entries.

**(c) Record the bump in `DECISIONS.md` in BOTH repos**, each linking commit
`2690b5b` and FR-003: framework decision = "consumer rule 6 reconciled to the
agent-required schema introduced in 2690b5b"; consumer decision = the
inviolate-rule-6 amendment with its attestation. **File the missing rule-6 proposal**
in `memory/brain/proposals.jsonl` (next free `P-008`) targeting `run-log` / consumer
rule 6, then route it to resolved once the decisions land — since the briefing's
`prop-82537922` is not on disk.

#### 🔒 HUMAN ATTESTATION REQUIRED

Inviolate rule 6 (`a_bgt_rsi/CLAUDE.md:151-154`) does not bend without explicit
human action. Amending it requires attestation:

- **VALUE** — Post-hoc human review can attribute *which agent did what*. With
  `agent` on every row, an auditor can reconstruct an unattended multi-agent run
  from the log alone and stitch "who used which skill, when, to what outcome" — the
  brain value the BOUNDARY contract assigns to the run log (the runtime EMITS the
  log; the brain READS it to learn).
- **REASON** — Rule 6 predates the multi-agent era (single-session, single-actor).
  It mandates a 6-field schema with no `agent`. Without `agent`, an unattended run
  that fanned out 6 build agents is anonymous-by-task-id and **cannot be audited** —
  demonstrated by 0/1004 attributed rows and 12 anonymous workflow rows already on
  disk.
- **PURPOSE** — Accountability when no human watched. D-040 ships unattended Nara
  autonomy at beta and explicitly rejected "always-on with no formal contract";
  attribution is the minimum that makes an unwatched run accountable rather than
  opaque. (D-040 is **ratified but inert until beta** — it takes effect at β.)

ATTESTATION REQUIRED FROM HUMAN before editing inviolate rule 6. Until attested,
this rule stands unchanged and parts (a)/(c) are inert; part (b) (adding entries) is
non-violating and may proceed independently since rule 6 sets a *minimum* schema.

**Data for the main session**

- Run-logger writer: `/home/decross1/projects/a_bgt_rsi/orchestrator/runtime.py:91-98`
  (`PyRuntime.log_event` does `row = {"timestamp": _utcnow_iso(), **event}`; never
  injects agent). Call sites: `/home/decross1/projects/a_bgt_rsi/orchestrator/nara.py`
  (~13 calls, e.g. `:354`, `:384`, `:478`, `:819`) — event dicts carry only domain
  keys, no agent.
- Field additions to consumer inviolate rule 6 (`a_bgt_rsi/CLAUDE.md:151-154`): add
  `agent` (REQUIRED) and `skill_used` (OPTIONAL). New schema: `{timestamp, task_id,
  agent, status, observable_actual, observable_expected, duration_ms, skill_used?}`.
  Matches framework FR-003 (`memory/brain/rules.md:24`) and run-log `SKILL.md:30-31`.
- Per-build-agent rows: emit `started` at fan-out + terminal (passed/failed/aborted)
  at join, `agent="workflow:wf_<id>/<role>"` (e.g. `workflow:wf_c4a70caf/B1`,
  `/integrator`). Satisfies CLAUDE.md Dynamic-Workflow-discipline item 5 + D-037 rule
  5 (`a_bgt_rsi/DECISIONS.md:1900`).
- Source commit to link in both DECISIONS.md: `2690b5b` (2026-05-27, "S24a: run-log
  schema gains agent + skill_used; agent and skill projected").
- Verified counts on `a_bgt_rsi/run_state/week1.run.jsonl`: 1004 total rows, agent
  0/1004, skill_used 0/1004; **12 anonymous Dynamic-Workflow rows (all agent:None),
  lines 886–981**.
- PROPOSAL DISCREPANCY: `prop-82537922` does NOT exist on disk (grep both repos → no
  match). `proposals.jsonl` uses P-NNN ids; P-001..P-007 all exist and are all
  closed; NO proposal scopes rule-6/run-log schema. Action: **FILE** the rule-6
  proposal as next free id (`P-008`) targeting run-log/consumer-rule-6, then resolve
  it — do not assume an existing record.
- `needs_human_attestation=true`: inviolate rule 6 edit requires explicit human
  attestation before parts (a)/(c). Part (b) adding rows is non-violating (rule 6 is
  a minimum schema) and may proceed independently.

---

## P1 — Remediation items (merge-gate, narrate-required, brain-recall) + P2 referenced-only record

Scope: the four items assigned (code-review gate disambiguation; narrate/propose as
required post-task steps; brain-recall on the build-agent path; the P2 referenced-only
record). Every claim below was ground-truthed by reading the named files on
2026-06-09. All four items concern the **consumer** repo
`/home/decross1/projects/a_bgt_rsi`. Items 1–3 edit the consumer operating contract
(`CLAUDE.md`) or its inviolate rules, so each carries an ATTESTATION block; item 4 is
a single additive DECISIONS.md note (consumer history is append-only) and also gets
one. The actual file edits are deferred to a human-attested apply step. (The
consumer's own `CLAUDE.md` is a **real file, not a symlink**, so edits there are
fine; only `CLAUDE.md → AGENTS.md` would be the symlink direction, which is not what
is edited here.)

---

### Item 1 — Disambiguate the merge-gate "code-review" (P1)

**Value.** Consumer `CLAUDE.md` line 64 reads: `... only after a verification gate:
code-review + full suite green + one real env -u MOCK_LLM smoke.` The bare token
`code-review` is ambiguous. In a Claude Code session `/code-review` resolves to the
**GitHub-PR builtin**, which reviews an open PR's diff. The consumer's merge model
has **no open PRs** — the primary session is the single commit authority and Dynamic
Workflows "return a report; they do not commit" (CLAUDE.md lines 64-66). So the
builtin would find no PR and **no-op to a falsely-clean gate**. The intended tool is
the **framework `code-review` skill**
(`/home/decross1/projects/agent_system/.agents/skills/code-review/SKILL.md`): an
adversarial pre-merge pass over a **local commit range / working diff** ("Read the
diff as an adversary: assume it is wrong and look for the proof"; checklist covers
scope, correctness, tests, and research-specific risks like silent metric changes and
train/eval leakage).

**Reason.** A merge gate that can silently pass because the wrong same-named tool
fired is exactly the "falsely-clean" failure the inviolate rules exist to prevent.
The two `code-review`s are not interchangeable: one needs an open PR, the other reads
`git diff`/a commit range locally. This is the merge-authority gate for the
apparatus's serial spine — the highest-consequence gate in the contract.

**Purpose.** Make the gate name the framework skill explicitly and state the
commit-range it reviews, so the gate cannot degrade to a no-op.

**Proposed change (consumer `CLAUDE.md`, line 64).** Replace the bare token with:
"`code-review` (the **framework `code-review` skill** — adversarial review of the
local commit range to be merged, i.e. `git diff <merge-base>..HEAD`; NOT the Claude
Code `/code-review` GitHub-PR builtin, which no-ops here because this repo merges via
the primary session with no open PR)". Low-risk doc clarification — narrows wording,
does not change the gate's substance.

#### 🔒 HUMAN ATTESTATION REQUIRED (item 1)
- **VALUE.** Edit one line of the consumer inviolate operating contract
  `/home/decross1/projects/a_bgt_rsi/CLAUDE.md` (the merge gate, line 64) to specify
  the framework `code-review` skill over the same-named GitHub-PR builtin.
- **REASON.** The bare token resolves to the builtin, which finds no open PR in this
  commit-authority merge model and passes the gate as a no-op (falsely clean).
- **PURPOSE.** Ensure the merge gate runs a real adversarial review of the local
  commit range before the single commit authority merges to the spine.

---

### Item 2 — Make narrate (and propose on a durable lesson) a REQUIRED post-task step (P1)

**Value.** The self-evolution loop is dormant. `memory/brain/narratives.jsonl` holds
**5 reflections, newest 2026-05-25T11:12Z** — ~15 days stale as of 2026-06-09 —
against **7363 apparatus_event** entries (newest 2026-06-09T03:51Z). June's real
operational lessons therefore live **only as deterministic apparatus_event noise**,
never as authored reflection: e.g. run-log task
`exp008_armC_unified_mem_freeze_incident` (`run_state/week1.run.jsonl` line 1002,
2026-06-08, status `recovered` — GB10 121GiB unified-memory thrash, "my util 0.46
guidance was too aggressive… STOP retrying arm C") and consumer commit `3b53380`
(2026-06-08, "exp008 harness hardening from the first live run (GB10 OOM +
error-as-zero)"). `narrate` exists precisely for this
(`.agents/skills/narrate/SKILL.md`: "captures the *why* and the lessons that the run
log's structured fields cannot"; pairs to the same `task_id`), and `brain-recall` is
meant to read these recent narratives to ground future work — but with the newest
reflection at May-vintage, that grounding is May-vintage. `narrate`/`propose` appear
**nowhere** in the consumer `CLAUDE.md` or `START_HERE.md` (grep returned empty), so
authoring them is currently nobody's job.

**Reason.** The brain's reflection layer only grows if some step is obligated to
write it. Today nothing obligates it, so it doesn't grow, so `brain-recall` returns
stale context, so the loop is closed in name only. The mechanism is sound (the
projected graph already carries 24 skill nodes / 48 skill edges from
harvest+proposals+spawn) — the missing piece is an authoring obligation at the points
where lessons are actually produced.

**Purpose.** Make apparatus learning become **authored brain signal**: require a
`narrate` entry at the Dynamic-Workflow **synthesize** phase and per Nara iteration,
and require a `propose` (to `memory/brain/proposals.jsonl`) when that reflection
surfaces a durable, named improvement (per the propose skill's own bar: a specific
durable change with a concrete `target`, not a one-off comment).

**Proposed change (consumer contract).** In `CLAUDE.md` §"Dynamic Workflow
discipline", extend the workflow run-logging rule (item 5, line 68) so the
**synthesize** phase additionally appends a `narrate` reflection (same `task_id` as
its run-log entry) to `memory/brain/narratives.jsonl`, and files a `propose` entry
when a durable lesson emerges. Apply the same requirement per Nara iteration once
D-040 unattended autonomy takes effect at β. Frame as "narrate is required; propose
is conditional on a durable lesson" so the gate is honest (narrate always; propose
only when there's a real target).

#### 🔒 HUMAN ATTESTATION REQUIRED (item 2)
- **VALUE.** Add a required `narrate` post-task step (and conditional `propose`) to
  the consumer `/home/decross1/projects/a_bgt_rsi/CLAUDE.md` Dynamic-Workflow
  synthesize phase and per Nara iteration.
- **REASON.** The brain reflection floor is ~15 days dormant (newest reflection
  2026-05-25); June lessons (exp008 GB10 OOM/error-as-zero, commit 3b53380) exist
  only as apparatus_event noise, so brain-recall grounding is May-vintage.
- **PURPOSE.** Convert apparatus learning into authored, recallable brain signal so
  the self-evolution loop is closed in fact, not just in name.

---

### Item 3 — Confirm/add brain-recall on the dev-time BUILD-AGENT task-start path (P1)

**Value.** There is **no trace** that `brain-recall` runs at build-agent task start
today: it is absent from the consumer `CLAUDE.md`, absent from `START_HERE.md`, and
the build agents' spawn-contract is **prose-only** (see firewall note below) so no
`skill_subset` enumerates it. `brain-recall` (`.agents/skills/brain-recall/SKILL.md`)
is the task-scoped grounding tier — "at task start, when the task touches a topic
where prior corrections or anomalies might apply" — and a build agent fanned out to
write a worker is exactly such a task.

**Reason.** Without brain-recall at task start, each build agent re-derives context
blind to prior corrections/anomalies (the very lessons item 2 is trying to make
authorable). Adding it to the build-agent **spawn-contract `skill_subset`** is the
correct, contract-bounded way to require it — the spawn-contract skill is explicit
that "Skill subset is closed": a child can only invoke skills its contract lists.

**Purpose.** Ground every dev-time build agent in prior corrections at task start, via
its spawn contract — read-only, bounded (the skill mandates a `limit` and
`token_cap`).

**BOUNDARY (state explicitly).** `brain-recall` is **Layer B, dev-time only** and goes
**only into the dev-time build-agent spawn-contract** — it must **NOT** be injected
into the **Nara RUNTIME worker prompts**. Per `BOUNDARY.md` and the brain-recall
skill's own "read this twice" boundary: the apparatus runtime **emits into** the brain
via ingest scripts but must **never read from** a developer-curated corpus about
itself — that is a self-reference loop with no external grounding. The runtime EMITS,
never READS the brain. This is consistent with the verified firewall (dev-only skills
must never load into the gemma/Nara runtime; only the runtime-safe skills may be
deliberately embedded). So: build-agent contract = add `brain-recall`; Nara runtime
worker prompts = do not add it.

**Proposed change (consumer contract).** In `CLAUDE.md` §"Dynamic Workflow discipline"
item 3 (spawn-contract per build agent, lines 59-62), add `brain-recall` to the
build-agent contract's `skill_subset` and require a brain-recall at the agent's
task-start, with an inline note that this applies to **dev-time build agents only and
must not propagate to Nara runtime worker prompts (runtime emits, never reads —
BOUNDARY firewall)**. Depends on item 5 below (materialize the spawn ledger first).

#### 🔒 HUMAN ATTESTATION REQUIRED (item 3)
- **VALUE.** Add `brain-recall` to the dev-time build-agent spawn-contract
  `skill_subset` in consumer `/home/decross1/projects/a_bgt_rsi/CLAUDE.md`
  (Dynamic-Workflow discipline, item 3), with an explicit boundary note excluding the
  Nara runtime.
- **REASON.** No trace today that build agents ground at task start; brain-recall is
  the dev-time task-scoped grounding tier, but it is BOUNDARY-forbidden in the runtime
  (apparatus emits into the brain, never reads from it).
- **PURPOSE.** Ground dev-time build agents in prior corrections at task start without
  breaching the runtime/dev-time firewall.

---

### Item 4 — P2 record: orchestrate / experiment / repro-check / plan-research are referenced-only (governed substitution)

**Value.** Four framework skills are **referenced-only** in the consumer:
`orchestrate`, `experiment`, `repro-check`, `plan-research`. Their function is
performed by the consumer's own **Dynamic-Workflow + verification gate** (governed
substitution), not by invoking the framework skill. The harvest feedback ledger
(`memory/feedback.jsonl`) keeps **re-flagging** several of them as coverage gaps
because harvest can't tell deliberate substitution from a real gap. (Distinguish from
item-2/3 skills: `code-review` and `slip-ladder` framework procedures DO fire; these
four are the genuinely-substituted set.)

**Reason.** A recurring harvest flag on an intentional design choice is noise that
masks real gaps. One durable, dated record of intent converts "looks like a gap" into
"decided, on the record" so future harvest passes can suppress it.

**Purpose.** Declare the substitution **intentional-of-record** so harvest stops
re-flagging these four.

**Proposed change.** Append a one-line **consumer** `DECISIONS.md` note (append-only;
new dated entry, next free id **D-041**): "orchestrate / experiment / repro-check /
plan-research are intentionally **referenced-only** — their function is met by the
Dynamic-Workflow + verification-gate substitution (D-037); do not treat their
non-invocation as a coverage gap. Re-flagged by harvest as a coverage gap:
**orchestrate (H002/H005/H007), experiment (H002), repro-check (H002/H003)**;
**plan-research is referenced-only by the same design choice though not itself
harvest-flagged** (substitution-of-record on design grounds, not harvest-noise
grounds)." This is a record, not a contract change.

#### 🔒 HUMAN ATTESTATION REQUIRED (item 4)
- **VALUE.** Append one dated note (append-only, D-041) to the consumer
  `/home/decross1/projects/a_bgt_rsi/DECISIONS.md` declaring
  orchestrate/experiment/repro-check/plan-research intentionally referenced-only.
- **REASON.** Consumer DECISIONS.md is append-only project history; even an additive
  note is a change to the consumer's decision record and should be human-confirmed.
- **PURPOSE.** Stop harvest from re-flagging a deliberate governed substitution as a
  coverage gap, with the verified harvest-ID mapping recorded so the note is accurate.

---

### Cross-cutting dependency (flagged)

Items 1–3 all live in `CLAUDE.md` §"Dynamic Workflow discipline". Item 3 in
particular presumes a **real** build-agent spawn-contract exists; today rule 3 (line
59) is **prose-only** — the live 2026-06-09 beta-hardening workflow fanned out 6
agents (A1–A4 assess, B1–B2 build) with **no spawn ledger** (no consumer
`run_state/spawn.jsonl`; the framework's `run_state/spawn.jsonl` holds 4 stale
2026-05-25 entries). So item 3's `skill_subset` edit should land **together with**
materializing the spawn ledger (the P0 spawn-contract item above), or it has no
`skill_subset` to attach to. Sequencing: materialize the spawn ledger first, then add
brain-recall to its build-agent contract.

**Data for the main session**

- Item 1 (code-review gate, P1, NEEDS ATTESTATION): consumer
  `/home/decross1/projects/a_bgt_rsi/CLAUDE.md` line 64 merge gate says bare
  `code-review`. Specify the FRAMEWORK code-review skill
  (`/home/decross1/projects/agent_system/.agents/skills/code-review/SKILL.md`)
  reviewing the local commit range `git diff <merge-base>..HEAD`; NOT the Claude Code
  `/code-review` GitHub-PR builtin (no open PRs in this commit-authority model →
  no-op → falsely-clean gate). Low-risk doc clarification.
- Item 2 (narrate/propose required, P1, NEEDS ATTESTATION): add required narrate (+
  conditional propose on durable lesson) to consumer `CLAUDE.md` Dynamic-Workflow
  synthesize phase (extend discipline rule 5, line 68) and per Nara iteration.
  Dormancy evidence: `memory/brain/narratives.jsonl` = 5 reflections, newest
  2026-05-25T11:12Z (~15d stale) vs 7363 apparatus_event; June lessons live only as
  apparatus_event noise (run-log task `exp008_armC_unified_mem_freeze_incident` line
  1002, consumer commit `3b53380` 2026-06-08). narrate/propose absent from consumer
  `CLAUDE.md` + `START_HERE.md`.
- Item 3 (brain-recall on build-agent path, P1, NEEDS ATTESTATION): no trace
  brain-recall runs at build-agent task start. Add brain-recall to the dev-time
  build-agent spawn-contract `skill_subset` in consumer `CLAUDE.md` discipline rule 3
  (lines 59-62). BOUNDARY: do NOT inject brain-recall into Nara RUNTIME worker prompts
  — runtime EMITS into the brain, never READS (`BOUNDARY.md` firewall; brain-recall is
  Layer B dev-time only). DEPENDS ON the spawn-ledger being materialized first (rule 3
  is prose-only today).
- Item 4 (referenced-only record, P2, NEEDS ATTESTATION for append): append one dated
  note (D-041) to consumer `/home/decross1/projects/a_bgt_rsi/DECISIONS.md` declaring
  orchestrate/experiment/repro-check/plan-research intentionally referenced-only
  (governed Dynamic-Workflow + verify-gate substitution per D-037). Verified harvest
  mapping: orchestrate → H002/H005/H007; experiment → H002; repro-check →
  H002/H003; plan-research → NOT currently harvest-flagged (substitution-of-record on
  design grounds). Distinct from code-review + slip-ladder which DO fire.
- VERIFICATION CORRECTION: proposal `prop-82537922` does NOT exist on disk.
  `proposals.jsonl` has only P-001..P-007, ALL latest-status=closed (open count 0).
  The rule-6/run-log schema bump is currently UNPROPOSED → recommend FILING it (next
  free `P-008`), do not cite an open proposal. Run-log: agent is REQUIRED in framework
  run-log SKILL (FR-003, commit 2690b5b); consumer inviolate rule 6 still 6-field;
  agent populated 0/1004 (file is 1004 lines).
- SEQUENCING: items 1–3 all edit consumer `CLAUDE.md` Dynamic Workflow discipline
  section. Item 3 has no `skill_subset` to attach to until the P0 spawn-contract
  ledger item materializes a real build-agent contract (live 2026-06-09 fan-out of 6
  agents A1–A4 assess / B1–B2 build had NO spawn ledger; no consumer
  `run_state/spawn.jsonl`; framework `spawn.jsonl` = 4 stale 2026-05-25 placeholder
  entries). Land spawn ledger first, then item 3.

---

## Already landed by the framework session (no action needed)

These are **DONE** in the `agent_system` repo — no main-session action required:

- **Doc-sync.** `AGENTS.md` / `BOUNDARY.md` / `README.md` / `plan.md` corrected from
  "five" → **"six" runtime-safe core**; `spawn-contract` added to the Layer-A table;
  the 5 missing Layer-B rows (**brain-recall, narrate, propose, review-proposal,
  slip-ladder**) added. New `scripts/check_doc_skill_counts.py` drift guard — passes
  (**A=6, B=13, C=5**).
- **Brain seeds.** 2 hand-authored nodes appended + projected —
  `correction-exp008-armc-gb10-unified-mem-oom-2026-06-09` and
  `reflection-exp008-error-as-zero-insufficient-2026-06-09` — with **3 lineage edges,
  0 new dangling**. The brain-recall correction/reflection floor is now **June-vintage
  instead of 13-day-stale**.

## BOUNDARY reminder

None of these changes inject any dev skill into the gemma/Nara **RUNTIME**. The
runtime **emits into the brain but never reads it**; `brain-recall` belongs **only in
dev-time build agents**. Items (b) of the run-log work and the spawn ledger thread
attribution/contracts through the runtime's *own* emitted artifacts — they do not put
any dev-time skill (brain-recall, narrate, propose, …) into a gemma worker prompt.
