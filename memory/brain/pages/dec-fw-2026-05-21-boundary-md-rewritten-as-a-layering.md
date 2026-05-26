---
slug: "dec-fw-2026-05-21-boundary-md-rewritten-as-a-layering"
type: "decision"
date: "2026-05-21"
source: "memory/DECISIONS.md"
---

# 2026-05-21 — BOUNDARY.md rewritten as a layering rule; runtime-safe core established

_framework decision_

**Decision:** `BOUNDARY.md`'s blanket "all skills are dev-time only" rule is
replaced by a two-class layering rule: **dev-only skills** (Layers B and C) that
must never enter a project's runtime agent, and a **runtime-safe core** (the 5
Layer-A skills — `resume-state`, `gate-check`, `validate`, `run-log`,
`fallback`) that may be *deliberately* embedded in a spawned / runtime agent.
`BOUNDARY.md` now defines the `runtime-safe` contract: no assumed human, no
dev-harness dependency, minimal context cost, no surprising side effects, a
closed dependency set. Per-skill conformance to that contract is verified in
Phase 3.
**Why:** The framework's goal (2026-05-21 re-scope) is to serve autonomously
spawned agents in any system, not only dev-time sessions. A blanket ban made the
framework's most general, most valuable asset — the execution-discipline core —
unusable where it is most needed. The dev-time/runtime line did not move; it
sharpened from "all skills" to "the dev-only layers."
**Supersedes:** the blanket rule of the 2026-05-18 "Scope boundary: dev-time vs
project-runtime" decision. The dev-time/runtime *distinction* that decision drew
still stands.
**Gate:** this decision reverses a standing rule; ratified by explicit human
go-ahead, 2026-05-21.
