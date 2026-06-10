---
slug: "dec-ap-d-048-test-pollution-purge-one-logged-surgical"
type: "decision"
date: "2026-06-10"
source: "a_bgt_rsi/DECISIONS.md"
---

# D-048 — Test-pollution purge (one logged surgical cleanup) + the autouse no-live-artifacts guard

_apparatus decision_

**Date locked.** 2026-06-10 (ratified by the human at planning time as an explicit
exception to append-only discipline).

**The finding.** Def-time-bound default paths let the test suite write LIVE apparatus
files for days: 23 synthetic "RuntimeError: boom" coordinator cycles (rendered as failed
dispatches on the dashboard), **3,930 of 4,819** `logs/calls.jsonl` rows with
`model:"fake-model"` (82% of the canonical call log), and 88 same-day worker_activity
rows. A second vector: `orchestrator/topicality.py` makes a REAL model call when
MOCK_LLM is unset — and MOCK_LLM is set in the human's interactive shell but NOT in
non-interactive shells, so test runs silently hit the live Gemma server and stamped
rows with a stale fixture run_id.

**Decision.** (a) One surgical purge with `.pre_purge_2026-06-10` backups kept beside
each file: coordinator_cycles 140→117 (−23 boom rows), calls.jsonl 4,819→879 (−3,930
fake-model − 10 test-context topicality rows), worker_activity 1,251→1,163 (−88; lands
exactly on the session-start baseline, confirming the dropped rows were all same-day
test artifacts). Malformed lines are never dropped. (b) The leak is closed structurally:
all writer defaults now resolve at CALL time (worker_activity, coordinator_cycle_log,
coordinator bubbles, nara's calls-log sentinel) and `tests/conftest.py` gains an
AUTOUSE `_no_live_artifacts` fixture redirecting every such default to tmp_path —
the invariant is "a full pytest run adds ZERO rows to run_state/, logs/, memory/".
(c) Operating rule: pytest runs are invoked with explicit `MOCK_LLM=1` (the inverse
discipline of `env -u MOCK_LLM` for real runs — do not rely on the shell default).
Stray finished-run redirects deleted (`run_state/battery_run*.log`,
`coordinator_cycle_evening.log`; battery artifacts live in
`experiments/lit_falsification_battery/runs/`); live server stdout (`tool_plane.out`,
`ui_backend.out`) stays in place (open fds) and is now gitignored along with the
registry dir and purge backups.

**Alternatives rejected.** Keeping the rows and rendering around them (UI ×N grouping)
— leaves failure triage and call-log forensics poisoned forever and the "canonical call
log" 82% synthetic. Append-only discipline is for research observations; these rows
were never observations.

**Reversibility.** Full: the `.pre_purge_2026-06-10` backups are byte-complete copies.
