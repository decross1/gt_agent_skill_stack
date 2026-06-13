---
slug: "dec-ap-d-049-interim-bounded-autonomy-the-coordinator"
type: "decision"
date: "2026-06-10"
source: "a_bgt_rsi/DECISIONS.md"
---

# D-049 — β-interim bounded autonomy: the coordinator may run unattended cycles ONLY under the pause/ledger/sentinel bounds (DRAFT — awaiting human ratification)

_apparatus decision_

**Date drafted.** 2026-06-10 (Session 3). **Status: DRAFT.** The
continuous-orchestrator guardrail (CLAUDE.md out-of-scope) stands unchanged until the
human ratifies this entry; D-040's unattended contract activates at β proper.

**Proposed decision.** Until β (Nara packaged in the sandbox), a bounded HOST-side
interim is permitted: scheduled coordinator cycles via `cron/run-coordinator.sh`,
gated by ALL of — (1) the ratification sentinel `run_state/d049_ratified` exists
(the human creates it to ratify; deleting it un-ratifies); (2) the kill switch
`run_state/pause_coordinator` does not exist (creating it halts every cycle,
checked before any LLM call — never bypassed, even supervised); (3) the daily
executed-cycle ledger `run_state/coordinator_budget.jsonl` stays within
`COORDINATOR_DAILY_CAP` (default 18 units/day ≈ 3 full cycles; dry-runs uncharged);
(4) the memory preflight (`preflight_mem_guard`, 30 GiB OS margin hard-pinned)
passes; (5) cycles run with `NARA_SKEPTIC=1` (the D-044-validated Qwen skeptic in
the critic seam). The action menu stays the validated constrained space (v2: +
`run_experiment` — committed-results bridge by default, real re-runs only with
explicit `run_real`; + `forecast_markets` — exp007 paper sweep, design-only, zero
trading surface). Supervised soaks (`tools/coordinator_soak.sh --i-am-supervising`,
human watching) may bypass ONLY the sentinel, never the pause file or ledger.

**To ratify:** `touch run_state/d049_ratified` and add the crontab line in
`cron/run-coordinator.sh`'s footer. **Reversibility:** delete the sentinel and/or
crontab line; create the pause file for an immediate halt.

**Alternatives rejected.** Unbounded host-side daemon (violates the guardrail's
intent); waiting for full β (forfeits months of bounded daily research throughput
the apparatus is now instrumented to run safely and the UI can observe).
