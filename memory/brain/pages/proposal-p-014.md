---
slug: "proposal-p-014"
type: "proposal"
date: "2026-06-10"
source: "memory/brain/proposals.jsonl"
---

# P-014 — Extract shared livePaths.ts walk-up helper in a_bgt_rsi frontend tests

_agent: claude-code-main_

**Verdict:** `open`

**Target:** skill → `a_bgt_rsi ui/frontend/tests`

**Change:** Dedupe the repo-root walk-up idiom now inlined (with cross-referencing comments) in test_revalidate_live_rows / test_validate_iterations / test_validate_lowevidence into one tests/livePaths.ts helper, per the 2026-06-10 handoff's original ask.

**Reasoning:** Three copies of path-resolution logic will drift; the handoff named a single shared helper as the fix shape.
