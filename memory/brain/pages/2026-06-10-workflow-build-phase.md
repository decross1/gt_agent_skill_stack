---
slug: "2026-06-10-workflow-build-phase"
type: "reflection"
date: "2026-06-10"
source: "memory/brain/narratives.jsonl"
---

# 2026-06-10-workflow-build-phase

**Intent:** Make the apparatus legible from the dashboard (every LLM call attributable to run/role/backend; concurrent runs visible; human gates resolvable from the UI) by shipping the EMIT side + a blessed write-back contract in one session, fanning the disjoint-new-file work to two workflow limbs while keeping spine edits, the ratified purge, integration, and the gate serial.

**Did:** Serial: backend/model provenance on all four call-record producers + worker-activity coverage (call_async/nara/subagent were blind spots); fixed the nara set_run_id leak via a mechanical registration wrapper; steps[] status board with dynamic redteam/ml_intern chips; registered six unregistered LLM entry points; todo_cli (ack/defer/list/close) + finding_session --set-status + docs/human_writeback_contract.md + CLAUDE.md triage step (D-046); call-time default resolution + autouse no-live-artifacts conftest guard + surgical purge with backups (D-048). Workflow wf_27141574-2c6: limb R built the multi-run registry in an isolated worktree (D-047), limb U authored the 538-line UI handoff doc; I integrated R, caught a regression, closed the ledger.

**Observed:** Three deltas from plan. (1) The pollution was 23x larger than scoped: 3,930 of 4,819 calls.jsonl rows were fake-model (82% of the canonical call log), not ~171 — tail-sampling under-measured it. (2) MOCK_LLM=1 is set only in the human's INTERACTIVE shell; non-interactive shells (tests, agents) run unmocked, so the suite had been making REAL Gemma calls via topicality.check and stamping them with a stale fixture run_id. (3) Limb R's worktree rewrite silently regressed the kind surface (dropped 'coordinator' from _KINDS and the schema enum); the existing join-contract test caught it at integration — the dictated-semantics prompt did not immunize against losing untouched-but-rewritten lines. Also found in passing: finding_session read finding.get('iteration_id') while promotion writes source_iteration_id, so every REAL promoted finding silently lost its iteration join.

**Would do differently:** When dictating a rewrite of an existing file to a limb, dictate the INVARIANTS to preserve (enums, public constants) as an explicit checklist, not just the new semantics — 'fix your implementation, not the test' caught one class of drift but only because a contract test existed. Verify environment assumptions (MOCK_LLM) with `env | grep` in the FIRST shell command of a session rather than trusting memory notes about the interactive shell. Measure pollution with a full scan, not a tail sample, before sizing a purge.

**Corrections honored:** D-043, D-044, D-045

## Referenced by

- `agent-claude-code-main` (agent) — **authored**
