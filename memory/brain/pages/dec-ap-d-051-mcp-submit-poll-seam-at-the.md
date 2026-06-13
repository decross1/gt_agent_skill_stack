---
slug: "dec-ap-d-051-mcp-submit-poll-seam-at-the"
type: "decision"
date: "2026-06-10"
source: "a_bgt_rsi/DECISIONS.md"
---

# D-051 — MCP submit+poll seam at the β tool plane (ticket store composed with the D-047 registry)

_apparatus decision_

**Date.** 2026-06-10 (session 2, workflow `wf_d4e96978-59a` limb b1 + serial
integration). Implements the direction recorded in the 2026-06-10 morning
note; closes the T2 known gap (OpenClaw MCP client 15s timeout vs the
~74–479s synchronous `run_loop_iteration`).

**Decision.** Two new tools beside the unchanged pair at
`orchestrator/tool_plane.py` — `submit_loop_iteration` (returns a
`mcpsub-…` ticket run_id in milliseconds) and `poll_run` (honest reads
only) — backed by NEW `orchestrator/submitted_run.py`: an atomic ticket
store under `run_state/tool_plane_submits/`, a single daemon executor
thread per submit (latch + the existing one-at-a-time guard; no queue, no
scheduler, no cancellation), thread body `set_current_agent("nemoclaw_agent")`
→ `write_active_run(ticket_id, "ad_hoc", …)` → run-log accepted-event →
`run_iteration(topic, source="nemoclaw_agent")` → ticket finished/failed +
terminal event → `finally` clear/reset/release. `poll_run` reports
running/finished/failed/unknown from the ticket + registry +
`active_iteration.json` (mtime as freshness; 900s informational stale flag;
pid-mismatch reconciles a dead-server orphan ticket honestly). The sandbox
can poll ONLY this seam's tickets — host iterations and experiment runs are
not pollable (containment). Sync `run_loop_iteration` stays byte-compatible
(T2 evidence + curl smokes unaffected); the D-040/continuous-running
guardrail is intact: submit is still single-shot, human/agent-triggered, one
in flight.

**Verification.** 14 hermetic seam tests + plane-level endpoint tests; suite
1158 green at integration; real-smoke decision rule per the recon design
(submit <2s; poll converges; verdict fields equal the `loop_memory.jsonl`
record; a sandbox MCP drive completes without the 15s timeout) — pending the
next GPU-idle window, see the session note.

**Reversibility.** New module + additive plane endpoints; the sync path is
unchanged (its in-flight refusal predicate gains `thread_live()`, refusing
strictly more, never less); removing the two tools restores the exact T2
surface.

**Review residuals (2026-06-10 two-reviewer gate, accepted as documented).**
(a) pid-reuse: a restarted server that coincidentally inherits the dead
writer's pid would report an orphan ticket "running" — astronomically
unlikely under Linux pid_max; accepted as a residual of the pid-based
design. (b) The busy refusal's `in_flight` field names the INNERMOST live
run (during most of a submitted run that is the nested `iter-…` doc, not
the mcpsub ticket) — honest, by design. (c) Single-process assumption
(in-process latch) documented in the module + runbook.

**REAL-SMOKE VERIFICATION (2026-06-13, host-side): the three host-driveable
clauses PASS.** Tool plane :8077 restarted on current code (`/health` now
lists all four tools incl. `submit_loop_iteration` + `poll_run`). Drove
`submit_loop_iteration` with an in-domain topic (QRE vs Nash in repeated
public goods): **submit returned in 9ms** (`mcpsub-20260613T023330Z-b3de`,
clause: <2s ✓). **Poll converged** running→finished over ~2m21s
(submitted 02:33:30Z → finished 02:35:51Z), with the honest intermediate
reads exercised (registry kind/heartbeat, `active_iteration` steps[] board
walking meta_review→hypothesize→…→journal_writer, a dynamic redteam→failed
chip, `stale:false`) ✓. **Verdict fields equal the `loop_memory.jsonl`
record** (iter-2026-06-13-001: novelty `novel`, critic `survives`,
low_confidence false, journal 075) ✓. Run-log carries `nemoclaw_agent`
`tool_plane_submit_accepted`/`tool_plane_submit_finished` events bracketing
the 40-row chain. **Remaining clause — sandbox MCP drive (no 15s timeout) —
NOT run**: it is the runbook's stretch/out-of-scope path (sandbox egress +
gRPC/h2), deferred to a sandbox-coordinated window. The seam is proven at
the host boundary; the end-to-end sandbox proof is the one open item.
