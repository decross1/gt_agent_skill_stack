---
slug: "harvest-h001-l3"
type: "harvest_finding"
date: "2026-05-21"
source: "memory/feedback.jsonl"
edges:
  - {type: about, dst: "skill-run-log", dst_type: "skill"}
---

# H001 — run-log:confirmed

_week1.run.jsonl L5 task=state_transition_

**Source skill:** `run-log`

**Class:** confirmed

**Ref:** week1.run.jsonl L5 task=state_transition

**Source project:** a_bgt_rsi

**Evidence:** A state transition (gate cleared, task moved to completed_tasks) is logged as its own standalone entry, not buried in another task's line. Matches run-log's 'state transitions get their own entries'.

## Links

- **about** → `skill-run-log` (skill)
