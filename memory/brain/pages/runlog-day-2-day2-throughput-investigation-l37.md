---
slug: "runlog-day-2-day2-throughput-investigation-l37"
type: "run_log_entry"
date: "2026-05-19"
source: "week1.run.jsonl:37"
---

# a_bgt_rsi: Nara — week1.run L37

_determine whether 29.75 tok/s is genuine or a measurement artifact_

**Did:** Investigated whether the failed check #3 (29.75 tok/s) is a short-completion measurement artifact. REFUTED. Linear fit latency_ms = 59.7 + 31.15*output_tokens: fixed per-call overhead is only 60 ms (prefill+network negligible); marginal dec…

**Observed:** status=passed day=day_2 duration_ms=0 fallback=None

## Referenced by

- `harvest-h002-l15` (harvest_finding) — **observed_in**
- `harvest-h002-l16` (harvest_finding) — **observed_in**
