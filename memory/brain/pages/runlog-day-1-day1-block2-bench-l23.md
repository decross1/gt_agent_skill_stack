---
slug: "runlog-day-1-day1-block2-bench-l23"
type: "run_log_entry"
date: "2026-05-18"
source: "week1.run.jsonl:23"
---

# a_bgt_rsi: Nara — week1.run L23

_single-stream decode tok/s in [50,110]; >=40 hard floor_

**Did:** median single-stream decode 32.03 tok/s (bench/day1.csv; 5 prompts, 256 max_tokens) — BELOW the plan hard floor of 40. CSV row-count check passes (6 lines). Investigation (notes/day1-bench-debug.md): cache-full NO (buff/cache 1.3GiB), therm…

**Observed:** status=failed day=day_1 duration_ms=0 fallback=None
