---
slug: "proposal-p-015"
type: "proposal"
date: "2026-06-10"
source: "memory/brain/proposals.jsonl"
---

# P-015 — Refresh heartbeat_at per step in active_runs registry files (EMIT side)

_agent: claude-code-main_

**Verdict:** `open`

**Target:** rule → `a_bgt_rsi run registry (D-047)`

**Change:** update_active_run/registry writers should re-stamp heartbeat_at on every step transition/narration update, not only at run start. Live observation 16:47Z: coordinator_83d9e696 showed heartbeat_at == ~started_at while current_step=dispatch was genuinely advancing — the NowBoard correctly painted it stale-amber at >120s, but the staleness was an EMIT artifact, not a hang.

**Reasoning:** The stale-amber signal is only trustworthy if heartbeats refresh; otherwise every >2min run reads as stale and the alarm trains the human to ignore it (alert-fatigue rule).
