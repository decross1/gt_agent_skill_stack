---
slug: "proposal-p-010"
type: "proposal"
date: "2026-06-09"
source: "memory/brain/proposals.jsonl"
edges:
  - {type: targets, dst: "skill-code-review", dst_type: "skill"}
---

# P-010 — Sequence code-review BEFORE the first expensive real-model measurement

_agent: claude-code-main_

**Verdict:** `open`

**Target:** skill → `code-review`

**Change:** Add to the code-review skill's 'When to use': when a change feeds an expensive measurement (a real-model battery, a long experiment run), run the review BEFORE launching the measurement — a reviewer-caught blocker invalidates the measurement, not just the code. Parallelizing review with the measurement only saves time when the review is clean.

**Reasoning:** 2026-06-09 evening (a_bgt_rsi): the review ran in parallel with a ~20-min real battery; it caught a blocker (R0 topicality silently dead via a dict-shaped test stub) that made the in-flight measurement meaningless — killed and re-run. The 1041-test-green suite missed it; only adversarial review caught it. Sequencing review first would have cost ~10 min of wall and saved a full GPU run.

**References:** `session-2026-06-09-evening`, `D-045`

## Links

- **targets** → `skill-code-review` (skill)
