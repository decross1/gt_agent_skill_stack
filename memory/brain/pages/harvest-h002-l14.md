---
slug: "harvest-h002-l14"
type: "harvest_finding"
date: "2026-05-21"
source: "memory/feedback.jsonl"
edges:
  - {type: about, dst: "skill-fallback", dst_type: "skill"}
  - {type: observed_in, dst: "runlog-day-1-day1-block2-vllm-serve-l17", dst_type: "run_log_entry"}
  - {type: observed_in, dst: "runlog-day-1-day1-block2-nemoclaw-router-l25", dst_type: "run_log_entry"}
---

# H002 — fallback:friction

_week1.run.jsonl L17 vs L25_

**Source skill:** `fallback`

**Class:** friction

**Ref:** week1.run.jsonl L17 vs L25

**Source project:** a_bgt_rsi

**Evidence:** L17's fallback selection was 'human-approved' before being taken; L25's auto-branched from D-008's pre-declaration. fallback treats taking a declared fallback as the agent's call once triggered; it does not address that the fallback selection may itself be gated on human approval.

**Plan candidate:** fallback: note that a fallback selection may itself be a gated action (run gate-check on the switch), distinct from an auto-branch off a pre-declaration.

## Links

- **about** → `skill-fallback` (skill)
- **observed_in** → `runlog-day-1-day1-block2-vllm-serve-l17` (run_log_entry)
- **observed_in** → `runlog-day-1-day1-block2-nemoclaw-router-l25` (run_log_entry)
