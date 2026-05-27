---
slug: "harvest-h003-l26"
type: "harvest_finding"
date: "2026-05-22"
source: "memory/feedback.jsonl"
edges:
  - {type: about, dst: "skill-validate", dst_type: "skill"}
  - {type: observed_in, dst: "runlog-day-5-day4-carryover-resolution-l82", dst_type: "run_log_entry"}
---

# H003 — validate:confirmed

_week1.run.jsonl L82; DECISIONS.md D-026_

**Source skill:** `validate`

**Class:** confirmed

**Ref:** week1.run.jsonl L82; DECISIONS.md D-026

**Source project:** a_bgt_rsi

**Evidence:** The mis-specified Day-4 criterion (>=30 entries, unreachable by design) was resolved by amending plan.yaml (D-026: arbitrary >=30 -> per-artifact record counts), not by coercing the result. The original partial_pass stays in the append-only run log; the resolution is recorded forward. Exactly the protocol H002's validate-friction finding (mis-specified criterion) called for — strong evidence that finding points the right way.

## Links

- **about** → `skill-validate` (skill)
- **observed_in** → `runlog-day-5-day4-carryover-resolution-l82` (run_log_entry)
