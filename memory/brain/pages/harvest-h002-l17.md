---
slug: "harvest-h002-l17"
type: "harvest_finding"
date: "2026-05-21"
source: "memory/feedback.jsonl"
edges:
  - {type: about, dst: "skill-code-review", dst_type: "skill"}
  - {type: observed_in, dst: "runlog-day-4-day4-post-review-b1-fix-l77", dst_type: "run_log_entry"}
  - {type: observed_in, dst: "runlog-day-4-day4-post-review-nits-l78", dst_type: "run_log_entry"}
---

# H002 — code-review:confirmed

_week1.run.jsonl L77,L78_

**Source skill:** `code-review`

**Class:** confirmed

**Ref:** week1.run.jsonl L77,L78

**Source project:** a_bgt_rsi

**Evidence:** A pre-push code-review caught BLOCKING finding B1 — a stale vllm_image_tag default on all 12 Day-4 records, a reproducibility regression — and grouped the rest as nits N1-N6 (applied N1/N2/N4/N5, skipped N3/N6 with reasons). Matches code-review's adversarial read, research-risk focus, and blocking/non-blocking/nit grouping.

## Links

- **about** → `skill-code-review` (skill)
- **observed_in** → `runlog-day-4-day4-post-review-b1-fix-l77` (run_log_entry)
- **observed_in** → `runlog-day-4-day4-post-review-nits-l78` (run_log_entry)
