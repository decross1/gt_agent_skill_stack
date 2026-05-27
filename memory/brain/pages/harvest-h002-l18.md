---
slug: "harvest-h002-l18"
type: "harvest_finding"
date: "2026-05-21"
source: "memory/feedback.jsonl"
edges:
  - {type: about, dst: "skill-ship", dst_type: "skill"}
  - {type: observed_in, dst: "runlog-day-2-day2-end-of-day-artifacts-l44", dst_type: "run_log_entry"}
  - {type: observed_in, dst: "runlog-day-3-5-day3-5-end-of-day-artifacts-l69", dst_type: "run_log_entry"}
---

# H002 — ship:confirmed

_week1.run.jsonl L44,L69_

**Source skill:** `ship`

**Class:** confirmed

**Ref:** week1.run.jsonl L44,L69

**Source project:** a_bgt_rsi

**Evidence:** End-of-day shipping verifies a clean tree and runs the test suite to green before committing ('All schema+wrapper tests pass: 11+21+9=41/41. Working tree clean', L69). Matches ship's verify-clean-state and run-full-suite steps.

## Links

- **about** → `skill-ship` (skill)
- **observed_in** → `runlog-day-2-day2-end-of-day-artifacts-l44` (run_log_entry)
- **observed_in** → `runlog-day-3-5-day3-5-end-of-day-artifacts-l69` (run_log_entry)
