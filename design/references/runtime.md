# Agent Runtime, Fleet Coordination & Trace Analytics (`design/references/runtime.md`)

## When to use
Use when designing or reviewing views of live agent execution, multi-agent coordination buses (`argon`, `codex`, `opus`, `sonnet`), quota burn envelopes, retry/fallback loops, or OpenTelemetry/JSONL execution traces (`run_state/spawn.jsonl`, `framework.run.jsonl`, `agent_fleet_bus`).Fixture: `design/evals/runtime_fixture.json`.

## Data contract
```json
{
  "agents": [
    {
      "agent_id": "argon",
      "status": "active",
      "last_seen_at": "2026-10-27T03:20:00Z",
      "heartbeat_age_sec": 45,
      "active_attempt_id": "att-901",
      "quota_used_pct": 38.5,
      "reserve_floor_pct": 15.0,
      "epistemic_label": "observed"
    }
  ],
  "spans": [
    {
      "span_id": "sp-1",
      "parent_id": null,
      "agent_id": "codex",
      "name": "task:build-portal",
      "status": "completed",
      "start_ms": 0,
      "duration_ms": 4200,
      "cost_tokens": 18400,
      "diff_loc": {"added": 120, "removed": 14},
      "evidence_ref": "git:11d8538"
    }
  ],
  "messages": [
    {
      "msg_id": "m-01",
      "timestamp": "2026-10-27T03:15:00Z",
      "sender": "argon",
      "recipient": "codex",
      "kind": "TASK",
      "summary": "Verify release pipeline sync across 4 UI surfaces"
    }
  ]
}
```

## Canonical views
1. **Fleet Liveness & Quota Swimlane Strip (`Which agent needs attention?`):**
   - **Question answered:** Which agent is running, waiting, retrying, failed, or has a stale heartbeat whose true state is unknown? How close is each agent to its subscription reserve floor?
   - **Visual encoding:** One horizontal row or compact card per fleet agent (`argon`, `codex`, `opus`, `sonnet`) showing:
     - Status badge with shape + color (`● Active`, `◐ Stale heartbeat`, `✕ Failed`, `◌ Idle`). **Crucial distinction:** A confirmed failure uses `--bad` (`✕ Failed`), whereas an old heartbeat without a completion event renders as `--warn` dashed (`◐ Stale observation · true state unknown`).
     - Horizontal bullet bar for quota envelope (`0%` → `100%`) with a vertical tick mark at `reserve_floor_pct` (`15%` or `20%`). If passive burn is uninstrumented, show a muted `"Passive probe not instrumented"` note instead of `UNKNOWN` errors.
   - **Default sort:** Attention-needing agents (`failed`, `stale`, `blocked`) first, then active, then idle.
2. **Agent-Prism 4-View Trace Inspector (`Where did a run diverge?`):**
   - **Question answered:** Which step caused a failure, retry loop, or latency/token spike, and what code/state diff did it produce?
   - **Visual encoding:**
     1. *Hierarchical Span Tree* with search and status icons.
     2. *Aligned Timeline & Cost Bar* (`duration_ms` width, `cost_tokens` intensity).
     3. *AGDebugger Overview Band*: compresses long histories so a stuck retry loop appears immediately as a flat, repetitive visual band.
     4. *Span & Step Diff Inspector* (AgentStepper pattern): displays selected step inputs, outputs, retries, and exact repo/state diff (`+added / -removed` or `evidence_ref`).
3. **Normalized Multi-Agent Mail Bus (`Who is coordinating with whom?`):**
   - **Question answered:** What `TASK`, `APPROVE`, `REQUEST_CHANGES`, `STATUS`, or `NOTE` messages passed between agents?
   - **Visual encoding:** Compact chronological sequence table or directed lane feed with filter chips by `kind` and `agent_id`, never raw JSON blobs.

## Interactions
- Selecting an agent filters the Mail Bus and Trace Timeline to that agent's spans and messages.
- Selecting a span or message opens its full payload, `evidence_ref`, and state diff in the inspector drawer.
- Filter chips toggle `Attention Needed`, `Active`, `Stale`, and message `kind`.

## Anti-patterns
- **Don't** conflate a stale heartbeat with a confirmed process crash; **do** label stale heartbeats as `stale observation (true state unknown)` with last-seen timestamp.
- **Don't** render uncalibrated passive burn metrics as giant red `"UNKNOWN"` alarms; **do** show the configured reserve floor (`15%`/`20%`) and label unmeasured telemetry calmly as `unmeasured`.
- **Don't** show deeply nested trace trees without a timeline width bar; **do** pair hierarchy with relative duration/token bars.

## Deterministic checks
- Every agent row displays both a status label and a timestamp or age.
- Stale states (`stale`) and failed states (`failed`) use distinct CSS classes/badges.
- Mail bus rows render normalized `kind` badges (`APPROVE`, `REQUEST_CHANGES`, `TASK`, `STATUS`, `NOTE`).

## Sources
- AgentLens (Lu et al., 2024) — progressive overview-to-detail trajectory analysis
- Evil Martians `agent-prism` (`github.com/evilmartians/agent-prism`, reviewed `2026-10-27`) — 4 canonical trace views
- AGDebugger (Epperson et al., Microsoft CHI 2025, `arXiv:2503.02068`) — long-history overview band & message reset
- AgentStepper (2026) — per-step repo diff inspection
- Langfuse & Arize Phoenix — OTel span normalization contracts
