---
slug: "dec-fw-2026-05-18-added-execution-discipline-skills"
type: "decision"
date: "2026-05-18"
source: "memory/DECISIONS.md"
---

# 2026-05-18 — Added execution-discipline skills

_framework decision_

**Decision:** Added 4 skills — `gate-check`, `validate`, `run-log`,
`resume-state` — and adapted `experiment` (autonomous loop section) and
`plan-research` (design-vs-execute pointer).
**Why:** Explored the primary consumer `/home/decross1/projects/a_bgt_rsi` — a
contract-governed, plan-driven research program (authoritative `plan.yaml`,
state-file resume, blocking human gates, JSONL run log, validations never
coerced). The original gstack-derived skills were a design/ship loop and did
not cover plan-execution discipline, which is this project's core need. The
gstack safety roles (`/careful`/`/freeze`/`/guard`) dropped on 2026-05-18 are,
reframed, exactly this gap. Skills stay general-purpose.
**Supersedes:** partially revises the 2026-05-18 scaffold decision's skill set.
