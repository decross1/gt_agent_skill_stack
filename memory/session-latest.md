# Session Handoff — latest

Transient snapshot, **overwritten each session** by the `context-save` skill.
Read by `context-restore` / `resume-state` at the start of the next session.
Durable decisions go to `DECISIONS.md`, not here.

---

**Date:** 2026-06-14
**Task:** `plan.md` Session 24 — overdue harvest + hardening assessment +
brain-UI proposal scoping.

**State:** Committed as `dc8de9e`. `current_session` 24 (v1.0 pending).

**What happened this session**
- **Harvest H008** over `a_bgt_rsi` (D-030..D-052, run-log L155–1541): 22
  findings appended to `memory/feedback.jsonl` (+22 `harvest_finding→skill`
  edges, first of their kind). 12 confirmed · 1 diverged · 6 friction · 3 gap.
  Watermark advanced to **D-052 / line 1541 / `f182f4b`**.
- **Backlog re-sorted** into `plan.md` (new S24 block, gaps→friction→policy)
  with a per-skill **hardening dashboard**.
- **Hardening:** ✅ hardened (5): `gate-check`, `validate`, `decision-log`,
  `code-review`, `investigate`. ◻ provisional (2, single-harvest): `plan-research`,
  `slip-ladder`. ❌ open (6): `run-log`, `spawn-contract`, `experiment`,
  `fallback`, `repro-check`, `orchestrate`. Recorded in `framework.state.json`.
- **Brain-UI proposal scoping** (per human direction, two-tier):
  - `project_summary.py`: `proposal_scope()` — only **framework** proposals
    reach the needs-you inbox + loop band; research (`a_bgt_rsi`) proposals
    (P-012/014/015/016/017) filtered out. `_item()` emits
    `actionable=(surface=='framework')`.
  - `dashboard.html`: apparatus/research inbox items (16 gate verdicts) are
    **view-only** ("resolve in the apparatus UI"); only framework items get a
    sign-off action.
  - `propose/SKILL.md`: durable `scope` field added. `verify_brain_view` 27/27.
  - P-009 / P-011 (discipline proposals) kept **framework** per human choice.

**In flight:** Nothing.

**Resume point (next session)**
- **Address the 6 open skills** (esp. the **D-032 BOUNDARY firewall divergence**
  — consumer installed all 24 skills with no runtime-safe filter — and the
  `run-log` enum frictions). These are P1/P2/P3 in the S24 backlog block.
- **v1.0 is still blocked**: Charter requires *every* Layer-A skill hardened +
  open_gaps=0 + Pi-verified + the uplift test. `spawn-contract` (Layer A) is
  open; uplift (S19–S20) remains deferred pending a second consumer.
- A re-harvest will confirm `plan-research`/`slip-ladder` (need one more clean
  pass to harden) and re-test the 6 open skills.

**Known dirty tree (intentional):** `memory/brain/pages/**` (≈410 lines),
`view/{index.json,map_data.js,summary*.{js,json},2026-06-14.md}`, and
`narratives.jsonl` (287 lines of daemon ingest) are **deterministic projection
churn** from the live `brain-watch` daemon (pids in `run_state/`), left
uncommitted by request. This is exactly **P-013**'s open question (regen-artifact
tracking policy). Regenerate with the watch pipeline; do not hand-edit.

**Brain snapshot (start of this session):** active rules 3 · 18.7 days since
last proposal closed · median time-to-resume 5.0m.
