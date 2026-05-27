---
slug: "runlog-day-6-day6-block2-orchestrator-router-l102"
type: "run_log_entry"
date: "2026-05-23"
source: "week1.run.jsonl:102"
---

# a_bgt_rsi: Nara — week1.run L102

_router decides nemoclaw-or-fallback path_

**Did:** `nemoclaw` binary not found (command not found); fallback branch selected per plan.yaml branches.on_failure -> day6_block2_orchestrator_with_fallback. Consistent with state.fallbacks_taken.day1_nemoclaw (NemoClaw never installed on Day 1).

**Observed:** status=passed day=day_6 duration_ms=2 fallback=None
