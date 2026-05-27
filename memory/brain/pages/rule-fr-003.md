---
slug: "rule-fr-003"
type: "rule"
date: "2026-05-27"
source: "memory/brain/rules.md (derived from DECISIONS.md)"
---

# FR-003 — run-log schema: agent (required) and skill_used (optional)

_framework active rule_

- **Imperative:** Extend the canonical run-log entry shape with two new fields:
`agent` (required) — the entity that ran the step (e.g. `nara`,
`claude-code-main`, `human:<id>`); and `skill_used` (optional) — the framework
skill this step is part of (e.g. `validate`, `fallback`), present only when
the entry is a skill invocation. Anonymous-by-task-id logs prevent the brain
from attributing skill use to a specific actor, which breaks the
`harvest → propose → rule` self-improvement loop the framework exists to run.
Existing entries (137 framework + 281 consumer) are unrewritten — append-only
honored — and projected via per-file canonicalization at read time
(`framework.run.jsonl` → claude-code-main, `week1.run.jsonl` → nara, etc.).
- **Source decision:** `2026-05-27` (2026-05-27)
- **Supersedes:** none — extends the [[run-log]] entry shape that was last

## Apparatus rules

_No `**Correction:**`-flagged decisions in apparatus decision log._

## Referenced by

- `dec-fw-2026-05-27-run-log-schema-agent-required-and` (correction) — **enacts**
