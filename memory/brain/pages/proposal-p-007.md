---
slug: "proposal-p-007"
type: "proposal"
date: "2026-05-25"
source: "memory/brain/proposals.jsonl"
---

# P-007 — Live-ish brain: cron-driven ingest + regen + auto-refresh

_agent: claude-code-main_

**Verdict:** `accepted`

**Target:** skill → `scripts/ingest_apparatus.py`

**Change:** Wrap ingest_apparatus.py + project_pages.py in a small refresh script. Optionally cron it (every 5min or 15min). Add a tiny periodic-fetch to graph.html that re-loads graph_data.js without a full page reload. Sliding-window default ('last 7d') makes new entries visible without zoom-out. Closes the user's 'is anything running right now?' question — brain becomes near-live rather than on-demand.

**Reasoning:** User feedback 2026-05-25: 'are all of these processes running right now? Maybe there is a current state, and a rewind...' Today the brain is strictly on-demand; nothing visible until project_pages.py runs. Even a 5-minute cron would make 'current activity' meaningful. The rewind/scrubber landed this session as part of the time-window control; the live half remains.

**References:** `ingest_apparatus.py`, `project_pages.py`, `serve_brain.sh`

**Verdict reasoning:** Implemented 2026-05-26: scripts/watch_brain.py (pure-stdlib polling daemon, debounce-fires the ingest -> project_pages -> render_brain pipeline on a_bgt_rsi/{run_state,memory,logs}/*.jsonl changes) + scripts/watch_brain.sh (start/stop/status/restart/tail/once lifecycle, mirrors serve_brain.sh). Brain firewall preserved: apparatus has no knowledge of the watcher. Verified end-to-end during this session — watcher caught iter-006 and iter-007 mid-session with ~3s lag from final write to graph_data.js update. Diverges from the proposal in mechanism (file-watcher beats cron — lower latency, no wasted no-op runs) but matches the intent. CAVEAT: the in-graph 'tiny periodic-fetch to reload graph_data.js without a full page reload' is NOT implemented. User still needs to hard-refresh to pick up updates. Filing a follow-up is worth considering if hard-refresh becomes friction.
