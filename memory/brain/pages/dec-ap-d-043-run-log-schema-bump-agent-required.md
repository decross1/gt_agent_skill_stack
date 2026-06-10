---
slug: "dec-ap-d-043-run-log-schema-bump-agent-required"
type: "decision"
date: "2026-06-09"
source: "a_bgt_rsi/DECISIONS.md"
---

# D-043 — run-log schema bump: `agent` (required) + `skill_used` (optional); inviolate rule 6 amended

_apparatus decision_

**Date locked.** 2026-06-09. Agent-governance harness cycle; HUMAN-ATTESTED amendment of an inviolate rule (rule 6 is inviolate -> required the human's explicit 2026-06-09 sign-off, per P-008's human-review routing).

**Amends.** Inviolate rule 6 in [`CLAUDE.md`](CLAUDE.md). The canonical run-log entry shape gains two fields; the rest of rule 6 (append-only, mandatory-per-task, state-transitions-as-first-class-entries) is unchanged.

**Decision.** `run_state/week1.run.jsonl` rows now carry `{timestamp, task_id, agent, status, observable_actual, observable_expected, duration_ms, skill_used?}`. `agent` is **required** — the entity that ran the step (`nara`, `claude-code-main`, `human:<id>`, or `workflow:<wf_id>/<role>` for a Dynamic-Workflow limb). `skill_used` is **optional**, present only when the row is a framework-skill invocation (e.g. `validate`, `fallback`). The 7-field shape is a **minimum, not a ceiling** (consistent with the project's organically-extended `status` vocabulary). **Existing rows are not rewritten** — append-only stands; pre-bump rows are canonicalized at read time (`week1.run.jsonl` -> `nara`) per the framework projector.

**Why now.** A 2026-06-09 skill-alignment review found the consumer run log had `agent` populated **0/1004** and the **12 Dynamic-Workflow rows anonymous** (all `agent:null`, `week1.run.jsonl` L886-981): you could see *that* a workflow ran, not *which* limb did what or *where* a step failed. D-037 rule 5 already asks for per-agent start+finish entries; this closes the attribution gap **before** D-040's unattended-Nara autonomy makes anonymous limbs un-reconstructible. It also restores the framework's `harvest -> propose -> rule` loop, which anonymous-by-task-id logs break.

**Provenance / links.** Mirrors framework rule **FR-003** (`agent_system/memory/brain/rules.md:24`, source decision 2026-05-27) and framework commit **`2690b5b`** ("S24a: run-log schema gains `agent` + `skill_used`; agent and skill projected", 2026-05-27). **Reconciles framework proposal P-008** (`agent_system/memory/brain/proposals.jsonl`, opened 2026-06-09, routed to human-review because it edits an inviolate consumer rule) — ratifying this entry is the consumer-side adoption P-008 requested; P-008 may be marked resolved on the framework side.

**What does NOT change.** Append-only (no row is ever edited or deleted to add `agent`); the per-task logging mandate; version pins; human gates; validations-never-coerced; MOCK_LLM discipline. The framework side already shipped (`run-log` SKILL.md requires `agent`, FR-003 codifies it, the projector reads it at ingest); this is the consumer catching up.

**Reversibility.** High. Drop the two fields from rule 6 and the writers stop emitting them; the read-time canonicalizer already tolerates rows that lack `agent` (it injects the per-file default), so historical rows need no migration either way.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>

---
