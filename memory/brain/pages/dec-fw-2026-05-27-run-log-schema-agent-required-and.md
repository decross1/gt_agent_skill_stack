---
slug: "dec-fw-2026-05-27-run-log-schema-agent-required-and"
type: "correction"
date: "2026-05-27"
source: "memory/DECISIONS.md"
edges:
  - {type: enacts, dst: "rule-fr-003", dst_type: "rule"}
---

# 2026-05-27 — run-log schema: agent (required) and skill_used (optional)

_framework decision_

**Correction:** Extend the canonical run-log entry shape with two new fields:
`agent` (required) — the entity that ran the step (e.g. `nara`,
`claude-code-main`, `human:<id>`); and `skill_used` (optional) — the framework
skill this step is part of (e.g. `validate`, `fallback`), present only when
the entry is a skill invocation. Anonymous-by-task-id logs prevent the brain
from attributing skill use to a specific actor, which breaks the
`harvest → propose → rule` self-improvement loop the framework exists to run.
Existing entries (137 framework + 281 consumer) are unrewritten — append-only
honored — and projected via per-file canonicalization at read time
(`framework.run.jsonl` → claude-code-main, `week1.run.jsonl` → nara, etc.).
**Alternatives considered:**
(a) Add a new runtime-safe `trace` skill alongside run-log — rejected: more
    surface area, no real benefit over evolving the existing skill.
(b) Filename-only heuristic, no schema change — rejected (this session's
    user choice): enshrines an inference layer that breaks when apparatus
    moves files; the heuristic should be a backward-compat fallback, not
    the steady state.
**Rationale:** `run-log` is already the runtime-safe Layer-A skill called on
every consequential step. Carrying agent in the entry shape closes the gap
in one place, vs. spreading the concern across N consumer-side adapters.
`skill_used` is optional because not every step is a skill phase — task
completion records that aren't tied to a specific skill omit it cleanly.
**Reversibility:** medium — the schema is backward-compatible (existing
entries without `agent` keep working via the projector's filename
canonicalization). Hardest part to undo is the convention shift in newly
authored run-log entries; revert would mean asking consumers to drop the
field again, which is mild churn but not data loss.
**Supersedes:** none — extends the [[run-log]] entry shape that was last
hardened in S10.

## Links

- **enacts** → `rule-fr-003` (rule)
