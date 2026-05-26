---
slug: "dec-fw-2026-05-24-reconcile-state-file-lag-against-run-log"
type: "correction"
date: "2026-05-24"
source: "memory/DECISIONS.md"
edges:
  - {type: enacts, dst: "rule-fr-002", dst_type: "rule"}
---

# 2026-05-24 — Reconcile state-file lag against run-log during gate-armed periods

_framework decision_

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

## Links

- **enacts** → `rule-fr-002` (rule)
