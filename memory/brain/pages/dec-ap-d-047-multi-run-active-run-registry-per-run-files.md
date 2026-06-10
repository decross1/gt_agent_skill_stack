---
slug: "dec-ap-d-047-multi-run-active-run-registry-per-run-files"
type: "decision"
date: "2026-06-10"
source: "a_bgt_rsi/DECISIONS.md"
---

# D-047 — Multi-run active-run registry (per-run files + foreground mirror)

_apparatus decision_

**Date locked.** 2026-06-10 (ratified at planning; built by Dynamic Workflow
`wf_27141574-2c6` limb R in an isolated worktree; serially integrated).

**Decision.** `orchestrator/active_run.py` becomes a multi-run registry: every live run
writes its own `run_state/active_runs/<safe(run_id)>.json` (schema-validated, atomic
write tmp + os.replace, deleted on completion) carrying `heartbeat_at`, refreshed on
every update — consumers treat a stale heartbeat as a possibly-dead run. Ownership is
keyed by a module-level ContextVar holding the run_id, so `write_active_run` /
`update_active_run` / `clear_active_run` keep their exact signatures and the ~10 call
sites are untouched. `run_state/active_run.json` stays as the foreground mirror (most
recent writer; the UI keeps polling just that file) with **only-owner-clears**: an
update never rewrites a mirror owned by a different run_id, and a context-keyed clear
deletes the mirror only when it owns it; legacy no-context clears remove the mirror
plus its per-run twin. Resolves loop-iteration / coordinator / battery runs clobbering
each other's live state (the screenshot-review "BUSY (unregistered)" / single-slot
failure mode). Registry path follows the mirror's parent when a test relocates only
ACTIVE_RUN_PATH ("the registry lives beside the mirror" invariant).

**Integration note (honest record).** The limb's worktree rewrite regressed the `kind`
surface to 4 kinds — dropping `coordinator` from both `_KINDS` and the schema enum
(present at HEAD since the Slice-Alpha coordinator landed). Caught by the existing
join-contract test at integration (`test_update_active_run_each_coordinator_step_is_
schema_valid`); restored before merge. Full suite 1068 green after integration.

**Alternatives.** (1) Thread run handles through every call site — rejected: ~12-file
churn for no safety gain. (2) Replace the mirror outright with the registry — rejected:
breaks the live UI contract mid-flight.

**Reversibility.** Delete RUNS_DIR + the contextvar; mirror behavior reverts to the
single-slot helper.
