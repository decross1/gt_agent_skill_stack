---
slug: "runlog-day-4-day4-post-review-b1-fix-l77"
type: "run_log_entry"
date: "2026-05-20"
source: "week1.run.jsonl:77"
---

# a_bgt_rsi: Nara — week1.run L77

_every Day-4 record carries vllm_image_tag=vllm/vllm-openai:v0.21.0; rate preserved; all tests pass_

**Did:** Pre-push code-review identified BLOCKING B1: agent_wrapper/wrapper.py HOST_METADATA default for vllm_image_tag was 'vllm/vllm-openai:v0.20.0', stale since Day-2's D-022 re-pin. All 12 Day-4 records carried the wrong tag, contradicting CLAUD…

**Observed:** status=passed day=day_4 duration_ms=0 fallback=None

## Referenced by

- `harvest-h002-l17` (harvest_finding) — **observed_in**
- `harvest-h002-l22` (harvest_finding) — **observed_in**
