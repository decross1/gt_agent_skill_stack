---
slug: "harvest-h003-l28"
type: "harvest_finding"
date: "2026-05-22"
source: "memory/feedback.jsonl"
edges:
  - {type: about, dst: "skill-run-log", dst_type: "skill"}
---

# H003 — run-log:friction

_week1.run.jsonl L88 task=day5_block2_pipeline_implementation_

**Source skill:** `run-log`

**Class:** friction

**Ref:** week1.run.jsonl L88 task=day5_block2_pipeline_implementation

**Source project:** a_bgt_rsi

**Evidence:** a_bgt_rsi logs status='escalated' (L88), adding to 'started' (H001) and 'partial_pass' (H002 L76) — three status values run-log's enum (passed|failed|aborted|halted|skipped) lacks, across three harvests. The enum is systemically incomplete; real plan-execution needs start, partial, and escalation states.

**Plan candidate:** run-log: expand the status enum (started/in_progress, partial_pass, escalated) or explicitly declare it a non-exhaustive default the project extends.

## Links

- **about** → `skill-run-log` (skill)
