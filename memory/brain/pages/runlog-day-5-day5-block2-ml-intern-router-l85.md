---
slug: "runlog-day-5-day5-block2-ml-intern-router-l85"
type: "run_log_entry"
date: "2026-05-21"
source: "week1.run.jsonl:85"
---

# a_bgt_rsi: Nara — week1.run L85

_router probes ML-Intern installability and branches to ml_intern_attempt (on_success) or pipeline_fallback (on_failure/on_timeout) within a 45-min cap_

**Did:** Router probe executed (~4 min wall clock, well under 45-min cap). plan.yaml router command has a literal <url> placeholder; resolved from the ml-intern PyPI package's own published metadata to https://github.com/huggingface/ml-intern.git (c…

**Observed:** status=passed day=day_5 duration_ms=240000 fallback=None

## Referenced by

- `harvest-h003-l27` (harvest_finding) — **observed_in**
