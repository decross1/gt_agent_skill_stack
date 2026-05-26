---
slug: "proposal-p-001"
type: "proposal"
date: "2026-05-24"
source: "memory/brain/proposals.jsonl"
---

# P-001 — Add reverse `linked_to` edge anomaly→correction for symmetry

_agent: claude-code-main_

**Verdict:** `auto-accept`

**Target:** edge → `edge:anomaly-tool-call-100pct→dec-fw-2026-05-24-treat-100-metrics-in-small-n`

**Change:** Append a new edge to edges.jsonl: src=anomaly-tool-call-100pct (anomaly), type=linked_to, dst=dec-fw-2026-05-24-treat-100-metrics-in-small-n (correction). The reverse already exists (correction references anomaly); this adds the explicit forward link from the anomaly's perspective.

**Reasoning:** Clean backlinks: today the anomaly page shows the correction in 'Referenced by' but doesn't surface it in 'Links'. Symmetric edges make the graph walk in both directions cleaner. Rule-aligned: no semantic change, no rule conflict, append-only.

**References:** `anomaly-tool-call-100pct`, `dec-fw-2026-05-24-treat-100-metrics-in-small-n`

**Verdict reasoning:** Append-only addition to edges.jsonl; no rule conflict in rules.md; no semantic change to existing entities; no touch to SKILL.md/DECISIONS.md/boundary. Falls inside the review-proposal auto-accept allowlist (backlinks regeneration / non-semantic addition). Applying: appending the edge.
