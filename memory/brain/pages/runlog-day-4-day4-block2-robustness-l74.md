---
slug: "runlog-day-4-day4-block2-robustness-l74"
type: "run_log_entry"
date: "2026-05-20"
source: "week1.run.jsonl:74"
---

# a_bgt_rsi: Nara — week1.run L74

_5 trials recorded; rate written to metric_log.day4_tool_call_invocation_rate_

**Did:** tests/test_tool_call_robustness.py --n 5 --temperature 0.3 against live vLLM (gemma4 tool parser). 5/5 runs invoked the tool. 10/10 records schema-valid (verify_log_integrity==0). 0 ToolCallError raised. Rate 1.00 written to run_state/week1…

**Observed:** status=passed day=day_4 duration_ms=0 fallback=None

## Referenced by

- `harvest-h002-l21` (harvest_finding) — **observed_in**
