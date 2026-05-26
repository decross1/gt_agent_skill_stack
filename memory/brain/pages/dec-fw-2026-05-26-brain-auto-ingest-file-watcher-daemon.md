---
slug: "dec-fw-2026-05-26-brain-auto-ingest-file-watcher-daemon"
type: "decision"
date: "2026-05-26"
source: "memory/DECISIONS.md"
---

# 2026-05-26 — Brain auto-ingest: file watcher daemon over cron

_framework decision_

**Decision:** `scripts/watch_brain.py` is a pure-stdlib polling daemon
(`scripts/watch_brain.sh` lifecycle wrapper, mirrors `serve_brain.sh`). It
polls `a_bgt_rsi/{run_state,memory,logs}/*.jsonl` mtime+size every 1s, debounces
1.5s after the last change, then fires `ingest_apparatus.py → project_pages.py
→ render_brain.py`. ~3s end-to-end latency from apparatus write to graph
update.
**Alternatives considered:**
(a) cron every 5min (P-007's original suggestion) — rejected: 5-min lag is too
    long for the "is anything running right now?" question, AND 95% of cron
    fires are no-ops (wasted invocations).
(b) Apparatus-side post-iteration hook — rejected: violates the brain firewall
    (apparatus would have to know about the brain).
(c) inotify / `watchfiles` dep — rejected: extra runtime dependency for a use
    case that pure-stdlib handles fine.
(d) systemd path unit — rejected: ties to a specific init system; less portable
    than a shell-wrapped Python process with pidfile + log.
**Rationale:** File-first + write-only-on-apparatus rails are non-negotiable.
The watcher reads apparatus JSONL only, never writes back. Polling is "slower"
than inotify but invisible at the human-feedback latency scale (~3s vs ~1s).
Idempotent pipeline + (file,line) dedup makes spurious wakeups cheap.
**Reversibility:** trivial — `scripts/watch_brain.sh stop` and remove the two
files. Brain returns to manual `ingest -> project -> render` runs.
**Supersedes:** none.
