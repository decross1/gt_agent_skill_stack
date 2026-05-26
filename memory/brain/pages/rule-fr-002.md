---
slug: "rule-fr-002"
type: "rule"
date: "2026-05-24"
source: "memory/brain/rules.md (derived from DECISIONS.md)"
---

# FR-002 — Reconcile state-file lag against run-log during gate-armed periods

_framework active rule_

- **Imperative:** Trust the run log over the state file when they disagree
across a gate-armed period.
- **Source decision:** `2026-05-24` (2026-05-24)
- **Supersedes:** none — extends [[resume-state]] step 5.

## Apparatus rules

_No `**Correction:**`-flagged decisions in apparatus decision log._

## Referenced by

- `dec-fw-2026-05-24-reconcile-state-file-lag-against-run-log` (correction) — **enacts**
