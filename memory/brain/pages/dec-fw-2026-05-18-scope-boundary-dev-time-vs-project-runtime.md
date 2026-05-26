---
slug: "dec-fw-2026-05-18-scope-boundary-dev-time-vs-project-runtime"
type: "decision"
date: "2026-05-18"
source: "memory/DECISIONS.md"
---

# 2026-05-18 — Scope boundary: dev-time vs project-runtime

_framework decision_

**Decision:** Established that this framework is a dev-time harness only; its
skills must not be loaded into any project's runtime agent. Added `BOUNDARY.md`
and a `## Scope boundary` section to `AGENTS.md` / `README.md`.
**Why:** Explored `a_bgt_rsi`'s architecture — its runtime orchestrator (Gemma 4
+ OpenClaw + NemoClaw) also runs on Pi. With the dev skills installed globally
in `~/.pi/agent/skills/`, the apparatus runtime could inherit them. The two
"orchestrators" (dev-time and apparatus-runtime) must stay separate.
**Supersedes:** none
