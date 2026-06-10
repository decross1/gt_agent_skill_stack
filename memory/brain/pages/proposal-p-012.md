---
slug: "proposal-p-012"
type: "proposal"
date: "2026-06-10"
source: "memory/brain/proposals.jsonl"
---

# P-012 — Prune stale day7/day8 worktrees in a_bgt_rsi

_agent: claude-code-main_

**Verdict:** `open`

**Target:** rule → `a_bgt_rsi worktree hygiene`

**Change:** Remove .claude/worktrees/day7-main and day8-main (clean, weeks-stale). Requires the owner's explicit attestation naming them — the 2026-06-10 ui-session removal attestation was correctly scoped to ui-session only.

**Reasoning:** Stale worktrees accumulate ref/locking risk; the locked wf_c4a70caf worktree also needs an unlock decision.
