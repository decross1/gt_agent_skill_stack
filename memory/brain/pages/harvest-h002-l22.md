---
slug: "harvest-h002-l22"
type: "harvest_finding"
date: "2026-05-21"
source: "memory/feedback.jsonl"
edges:
  - {type: about, dst: "skill-repro-check", dst_type: "skill"}
---

# H002 — repro-check:confirmed

_week1.run.jsonl L39,L77; DECISIONS.md D-017,D-022_

**Source skill:** `repro-check`

**Class:** confirmed

**Ref:** week1.run.jsonl L39,L77; DECISIONS.md D-017,D-022

**Source project:** a_bgt_rsi

**Evidence:** Reproducibility discipline is pervasive: determinism re-checked 3x at T=0 and T=1/seed=42 (L39); the vLLM image pinned by SHA digest not tag (D-017, D-022); code-review B1 caught records carrying a stale image tag (L77). Matches repro-check's seed-control, environment-pinning, and code-provenance checks.

## Links

- **about** → `skill-repro-check` (skill)
