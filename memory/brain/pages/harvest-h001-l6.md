---
slug: "harvest-h001-l6"
type: "harvest_finding"
date: "2026-05-21"
source: "memory/feedback.jsonl"
edges:
  - {type: about, dst: "skill-gate-check", dst_type: "skill"}
  - {type: observed_in, dst: "runlog-day-1-state-transition-l5", dst_type: "run_log_entry"}
  - {type: observed_in, dst: "runlog-day-1-preflight-failure-walkthroughs-l7", dst_type: "run_log_entry"}
  - {type: observed_in, dst: "runlog-day-1-preflight-physical-setup-l8", dst_type: "run_log_entry"}
---

# H001 — gate-check:friction

_week1.run.jsonl L5 vs L7-L8_

**Source skill:** `gate-check`

**Class:** friction

**Ref:** week1.run.jsonl L5 vs L7-L8

**Source project:** a_bgt_rsi

**Evidence:** L5 clears a pending gate because a verifiable check passed (credentials present); L7-L8 clear gates by explicit human attestation. gate-check says gates clear only by 'explicit human action' and does not distinguish a gate cleared by attestation from one cleared by a checkable fact.

**Plan candidate:** gate-check: distinguish attestation-cleared gates from verification-cleared gates (gate condition is a checkable fact).

## Links

- **about** → `skill-gate-check` (skill)
- **observed_in** → `runlog-day-1-state-transition-l5` (run_log_entry)
- **observed_in** → `runlog-day-1-preflight-failure-walkthroughs-l7` (run_log_entry)
- **observed_in** → `runlog-day-1-preflight-physical-setup-l8` (run_log_entry)
