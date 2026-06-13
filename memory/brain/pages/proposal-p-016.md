---
slug: "proposal-p-016"
type: "proposal"
date: "2026-06-10"
source: "memory/brain/proposals.jsonl"
---

# P-016 — Dashboard-started iterations should record seed.source=human_ui

_agent: claude-code-main_

**Verdict:** `open`

**Target:** rule → `a_bgt_rsi POST /api/loop_v0/start`

**Change:** The start endpoint spawns loop_v0_cli without --source, so UI-kicked iterations record the CLI default human_cli (observed on iter-2026-06-10-003). Pass --source human_ui from the endpoint, mirroring the D-046 identity convention (human:ui stamps on write-backs).

**Reasoning:** Provenance honesty: the surface that initiated a run is part of its lineage; UI vs CLI initiation currently indistinguishable.
