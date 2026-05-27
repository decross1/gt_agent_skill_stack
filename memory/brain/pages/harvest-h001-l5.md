---
slug: "harvest-h001-l5"
type: "harvest_finding"
date: "2026-05-21"
source: "memory/feedback.jsonl"
edges:
  - {type: about, dst: "skill-gate-check", dst_type: "skill"}
  - {type: observed_in, dst: "runlog-day-1-preflight-failure-walkthroughs-l7", dst_type: "run_log_entry"}
  - {type: observed_in, dst: "runlog-day-1-preflight-physical-setup-l8", dst_type: "run_log_entry"}
---

# H001 — gate-check:confirmed

_week1.run.jsonl L7-L8 tasks=preflight_failure_walkthroughs,preflight_physical_setup_

**Source skill:** `gate-check`

**Class:** confirmed

**Ref:** week1.run.jsonl L7-L8 tasks=preflight_failure_walkthroughs,preflight_physical_setup

**Source project:** a_bgt_rsi

**Evidence:** Two human-only preflight tasks are marked passed via 'human attestation (decross1) ... not agent-verified' — the agent did not execute or verify them. Matches gate-check's 'human-only work — the agent does not execute it'.

## Links

- **about** → `skill-gate-check` (skill)
- **observed_in** → `runlog-day-1-preflight-failure-walkthroughs-l7` (run_log_entry)
- **observed_in** → `runlog-day-1-preflight-physical-setup-l8` (run_log_entry)
