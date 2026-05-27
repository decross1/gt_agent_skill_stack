---
slug: "harvest-h002-l23"
type: "harvest_finding"
date: "2026-05-21"
source: "memory/feedback.jsonl"
edges:
  - {type: about, dst: "skill-orchestrate", dst_type: "skill"}
  - {type: observed_in, dst: "runlog-day-3-track-review-track-b-l54", dst_type: "run_log_entry"}
  - {type: observed_in, dst: "runlog-day-3-track-review-track-c-l55", dst_type: "run_log_entry"}
  - {type: observed_in, dst: "runlog-day-3-track-review-track-d-l56", dst_type: "run_log_entry"}
  - {type: observed_in, dst: "runlog-day-3-adversarial-review-integration-l57", dst_type: "run_log_entry"}
  - {type: observed_in, dst: "runlog-day-3-merge-track-b-l58", dst_type: "run_log_entry"}
  - {type: observed_in, dst: "runlog-day-3-merge-track-c-l59", dst_type: "run_log_entry"}
  - {type: observed_in, dst: "runlog-day-3-merge-track-d-l60", dst_type: "run_log_entry"}
  - {type: observed_in, dst: "runlog-day-4-merge-track-c-day4-pd-strategies-l79", dst_type: "run_log_entry"}
  - {type: observed_in, dst: "runlog-day-4-merge-track-d-day4-ui-sync-l80", dst_type: "run_log_entry"}
---

# H002 — orchestrate:gap

_week1.run.jsonl L54-L60,L79-L80_

**Source skill:** `orchestrate`

**Class:** gap

**Ref:** week1.run.jsonl L54-L60,L79-L80

**Source project:** a_bgt_rsi

**Evidence:** a_bgt_rsi runs a 4-track parallel system on git worktrees with discipline orchestrate does not mention: per-track file-boundary allow-lists (L54-56 'File-boundary check PASS'), pre-merge boundary verification ('git diff --name-only main..worktree-X', L79-80), a '--no-ff' merge protocol (L58-60), mock-LLM isolation for side tracks, and completion sentinels ('TRACK C COMPLETE — ready to merge'). orchestrate covers role decomposition but not parallel-worktree execution.

**Plan candidate:** orchestrate (or a new skill): add a parallel-worktree execution protocol — per-track file-boundary allow-lists, mock isolation, pre-merge boundary verification, --no-ff merges, completion sentinels.

## Links

- **about** → `skill-orchestrate` (skill)
- **observed_in** → `runlog-day-3-track-review-track-b-l54` (run_log_entry)
- **observed_in** → `runlog-day-3-track-review-track-c-l55` (run_log_entry)
- **observed_in** → `runlog-day-3-track-review-track-d-l56` (run_log_entry)
- **observed_in** → `runlog-day-3-adversarial-review-integration-l57` (run_log_entry)
- **observed_in** → `runlog-day-3-merge-track-b-l58` (run_log_entry)
- **observed_in** → `runlog-day-3-merge-track-c-l59` (run_log_entry)
- **observed_in** → `runlog-day-3-merge-track-d-l60` (run_log_entry)
- **observed_in** → `runlog-day-4-merge-track-c-day4-pd-strategies-l79` (run_log_entry)
- **observed_in** → `runlog-day-4-merge-track-d-day4-ui-sync-l80` (run_log_entry)
