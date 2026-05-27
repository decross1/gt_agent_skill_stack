---
slug: "runlog-day-2-day2-block2-50call-sweep-l34"
type: "run_log_entry"
date: "2026-05-18"
source: "week1.run.jsonl:34"
---

# a_bgt_rsi: Nara — week1.run L34

_50 lines, 0 malformed, aggregate tok/s >= 40, T=0 and T=1/seed=42 determinism all identical_

**Did:** 5-check validation: #1 50 JSONL lines PASS (wc -l=50); #2 malformed=0 PASS (verify_log_integrity); #3 aggregate tok/s 29.75 FAIL (plan floor 40, computed output_tokens/sum-latency_ms across 50 calls); #4 T=0 determinism PASS (['391','391','…

**Observed:** status=failed day=day_2 duration_ms=0 fallback=None

## Referenced by

- `harvest-h002-l10` (harvest_finding) — **observed_in**
