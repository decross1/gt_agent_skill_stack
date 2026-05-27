---
slug: "harvest-h002-l13"
type: "harvest_finding"
date: "2026-05-21"
source: "memory/feedback.jsonl"
edges:
  - {type: about, dst: "skill-fallback", dst_type: "skill"}
  - {type: observed_in, dst: "runlog-day-1-day1-block2-vllm-serve-l17", dst_type: "run_log_entry"}
  - {type: observed_in, dst: "runlog-day-1-day1-block2-nemoclaw-router-l25", dst_type: "run_log_entry"}
---

# H002 — fallback:confirmed

_week1.run.jsonl L17,L25_

**Source skill:** `fallback`

**Class:** confirmed

**Ref:** week1.run.jsonl L17,L25

**Source project:** a_bgt_rsi

**Evidence:** Two fallbacks taken cleanly: L17 MTP->NVFP4 baseline ('FALLBACK SELECTED', fallback_taken field set); L25 NemoClaw->plain-Docker (per D-008 pre-declaration + 90-min cap). Both are explicit named alternatives, logged as their own event with a fallback_taken field. Matches fallback's explicit/logged requirements.

## Links

- **about** → `skill-fallback` (skill)
- **observed_in** → `runlog-day-1-day1-block2-vllm-serve-l17` (run_log_entry)
- **observed_in** → `runlog-day-1-day1-block2-nemoclaw-router-l25` (run_log_entry)
