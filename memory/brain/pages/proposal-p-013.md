---
slug: "proposal-p-013"
type: "proposal"
date: "2026-06-10"
source: "memory/brain/proposals.jsonl"
---

# P-013 — Decide tracking policy for regenerated brain view artifacts

_agent: claude-code-main_

**Verdict:** `open`

**Target:** rule → `memory/brain/view tracking`

**Change:** Either gitignore derived view artifacts (map_data.js, summary_data.js, summary.json, index.json, pages churn) with periodic snapshot commits, or keep tracking but always isolate regen churn in dedicated commits (today's pattern).

**Reasoning:** The watch daemon dirties the tree continuously; today it blocked a merge mid-integration (resolved by committing churn separately). Append-only sources stay tracked either way.
