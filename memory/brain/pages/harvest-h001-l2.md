---
slug: "harvest-h001-l2"
type: "harvest_finding"
date: "2026-05-21"
source: "memory/feedback.jsonl"
edges:
  - {type: about, dst: "skill-run-log", dst_type: "skill"}
  - {type: observed_in, dst: "runlog-day-1-preflight-credentials-staged-l2", dst_type: "run_log_entry"}
  - {type: observed_in, dst: "runlog-day-1-preflight-credentials-staged-l3", dst_type: "run_log_entry"}
---

# H001 — run-log:confirmed

_week1.run.jsonl L2->L3 task=preflight_credentials_staged_

**Source skill:** `run-log`

**Class:** confirmed

**Ref:** week1.run.jsonl L2->L3 task=preflight_credentials_staged

**Source project:** a_bgt_rsi

**Evidence:** The task fails (L2) then passes on re-run (L3) as a new appended entry; the failed entry is never edited. Matches run-log's 'append only — a correction is a new entry'.

## Links

- **about** → `skill-run-log` (skill)
- **observed_in** → `runlog-day-1-preflight-credentials-staged-l2` (run_log_entry)
- **observed_in** → `runlog-day-1-preflight-credentials-staged-l3` (run_log_entry)
