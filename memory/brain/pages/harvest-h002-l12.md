---
slug: "harvest-h002-l12"
type: "harvest_finding"
date: "2026-05-21"
source: "memory/feedback.jsonl"
edges:
  - {type: about, dst: "skill-validate", dst_type: "skill"}
  - {type: observed_in, dst: "runlog-day-4-day4-end-of-day-artifacts-l76", dst_type: "run_log_entry"}
---

# H002 — validate:friction

_week1.run.jsonl L76 task=day4_end_of_day_artifacts_

**Source skill:** `validate`

**Class:** friction

**Ref:** week1.run.jsonl L76 task=day4_end_of_day_artifacts

**Source project:** a_bgt_rsi

**Evidence:** a_bgt_rsi needed a partial_pass verdict for a task executed correctly where one sub-check's threshold is itself mis-specified (entries>=30, unreachable by design) — distinct from coercion. validate's verdict set is only pass/fail/inconclusive; run-log's status enum likewise lacks partial_pass (cf. H001 enum finding).

**Plan candidate:** validate + run-log: consider a partial_pass verdict/status for 'executed correctly, a sub-check is a reported finding', kept distinct from coercion.

## Links

- **about** → `skill-validate` (skill)
- **observed_in** → `runlog-day-4-day4-end-of-day-artifacts-l76` (run_log_entry)
