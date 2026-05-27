---
slug: "harvest-h002-l21"
type: "harvest_finding"
date: "2026-05-21"
source: "memory/feedback.jsonl"
edges:
  - {type: about, dst: "skill-experiment", dst_type: "skill"}
  - {type: observed_in, dst: "runlog-day-4-day4-block2-robustness-l74", dst_type: "run_log_entry"}
---

# H002 — experiment:friction

_week1.run.jsonl L74 metric field; DECISIONS.md D-021_

**Source skill:** `experiment`

**Class:** friction

**Ref:** week1.run.jsonl L74 metric field; DECISIONS.md D-021

**Source project:** a_bgt_rsi

**Evidence:** a_bgt_rsi records experiment-shaped results (E1 clock experiment D-021; throughput before/after D-022; metric fields on run-log entries) but keeps no separate experiments.md — it uses the run log, state.metric_log, and DECISIONS.md. experiment mandates a separate memory/experiments.md ledger, a parallel store this project deliberately did not want.

**Plan candidate:** experiment: allow the experiment ledger to be the run log itself (a tagged entry) rather than mandating a separate experiments.md.

## Links

- **about** → `skill-experiment` (skill)
- **observed_in** → `runlog-day-4-day4-block2-robustness-l74` (run_log_entry)
