---
slug: "harvest-h006-l37"
type: "harvest_finding"
date: "2026-05-24"
source: "memory/feedback.jsonl"
edges:
  - {type: about, dst: "skill-resume-state", dst_type: "skill"}
---

# H006 — resume-state:friction

_week1.run.jsonl L137 task=day7_state_close_out_and_advance_to_day_8_

**Source skill:** `resume-state`

**Class:** friction

**Ref:** week1.run.jsonl L137 task=day7_state_close_out_and_advance_to_day_8

**Source project:** a_bgt_rsi

**Evidence:** After the publication-review gate cleared at L136, the consumer backfilled 16 day_7 task IDs into state.completed_tasks that had been *absent during the gate-armed hold*. The run-log had the tasks (L111-L127 over Day 7); the state file did not, until backfill. resume-state's rule is 'state file is authoritative on resume — reconcile with reality.' During a gate-armed hold, the state lagged the run-log by 16 entries; a resume during the hold would have either re-run completed work or accepted an incomplete state-file picture. The protocol does not say whether (a) the state file should be updated during a hold, or (b) resume-state should detect post-hold lag automatically.

**Plan candidate:** resume-state: explicit rule for state-file updates during a gate-armed hold (either: write through to state during hold OR detect run-log/state divergence at resume and reconcile by trusting run-log).

## Links

- **about** → `skill-resume-state` (skill)
