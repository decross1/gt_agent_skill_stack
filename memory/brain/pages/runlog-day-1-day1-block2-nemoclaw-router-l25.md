---
slug: "runlog-day-1-day1-block2-nemoclaw-router-l25"
type: "run_log_entry"
date: "2026-05-18"
source: "week1.run.jsonl:25"
---

# a_bgt_rsi: Nara — week1.run L25

_branch to primary (probe ok) or fallback (probe fails)_

**Did:** router probe — nemoclaw README present, node v22.22.2 present, but 'which nemoclaw' fails (binary not installed); probe exits non-zero -> on_failure branch. Routing to day1_block2_nemoclaw_fallback (plain-Docker). NemoClaw primary onboardin…

**Observed:** status=passed day=day_1 duration_ms=0 fallback=day1_nemoclaw: NemoClaw -> hardened plain-Docker

## Referenced by

- `harvest-h002-l13` (harvest_finding) — **observed_in**
- `harvest-h002-l14` (harvest_finding) — **observed_in**
