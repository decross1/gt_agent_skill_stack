---
slug: "harvest-h001-l4"
type: "harvest_finding"
date: "2026-05-21"
source: "memory/feedback.jsonl"
edges:
  - {type: about, dst: "skill-run-log", dst_type: "skill"}
  - {type: observed_in, dst: "runlog-day-1-day-1-start-l1", dst_type: "run_log_entry"}
---

# H001 — run-log:friction

_week1.run.jsonl L1 task=day_1_start_

**Source skill:** `run-log`

**Class:** friction

**Ref:** week1.run.jsonl L1 task=day_1_start

**Source project:** a_bgt_rsi

**Evidence:** The entry uses status='started' for a session-start marker. run-log's status enum is passed|failed|aborted|halted|skipped — it does not anticipate start/in-progress markers that real run logs use.

**Plan candidate:** run-log: state the status enum is a non-exhaustive default, or add 'started'/'in_progress'.

## Links

- **about** → `skill-run-log` (skill)
- **observed_in** → `runlog-day-1-day-1-start-l1` (run_log_entry)
