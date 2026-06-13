---
slug: "dec-fw-2026-06-13-housekeeping-reconcile-the-2026-06-10-ui"
type: "correction"
date: "2026-06-13"
source: "memory/DECISIONS.md"
---

# 2026-06-13 — Housekeeping: reconcile the 2026-06-10 UI move (state write-forward)

_framework decision_

**Decision.** Close out the 2026-06-10 two-surface UI overhaul as drift cleanup:
(1) write the run log forward into `framework.state.json` — append the six
`ui_overhaul_*` tasks (run log L138–143, all `passed`) to `completed_tasks` and
refresh `value_metrics`; `current_session` stays 24 (the overhaul was out-of-band
work, not a numbered plan session). (2) Retire stale `graph_data.js` references in
`project_summary.py` / `project_pages.py` (file deleted in the overhaul; data now
lives in `summary.json` / `summary_data.js` / `map_data.js`). (3) Point
`serve_brain.sh` at `dashboard.html` (the post-overhaul primary surface, not
`graph.html`) and correct the `watch_brain.{py,sh}` pipeline docstrings to the real
five steps (ingest → project_pages → project_map → project_summary → render).
(4) Remove the merged `brain-overhaul` worktree + branch. Found and verified by an
adversarial discover→verify→critic workflow (18 confirm / 6 needs-human / 6 reject).

**Correction:** When a state file lags the run log across a shipped-but-unrecorded
work burst, write the state forward from the run log rather than leaving the lag —
the run log is canonical (per the 2026-05-24 correction), and resume-state's
write-through is the prescribed reconciliation, not an optional nicety.

**Alternatives.** Leave the state lag and rely on resume-state's run-log
reconciliation each session (rejected: the divergence re-surfaces every resume and
invites re-running done work); bump `current_session` past 24 (rejected: the
overhaul wasn't a numbered session — would misnumber the plan).

**Rationale.** The 442-file projection churn + state lag + stale UI docs were the
visible drift from shipping the overhaul without a closing reconciliation pass.
Recording it keeps the audit trail honest and the next resume clean.

**Reversibility.** High — all edits are doc/comment/state-record changes; no code
behavior changed; the four verifiers (verify_brain_view, doc-counts,
design-tokens, pi-discovery) gate the result.
**Supersedes:** none — extends the 2026-06-10 design-system entry above.
