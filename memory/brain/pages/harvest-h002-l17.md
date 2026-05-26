---
slug: "harvest-h002-l17"
type: "harvest_finding"
date: "2026-05-21"
source: "memory/feedback.jsonl"
---

# H002 — code-review:confirmed

_week1.run.jsonl L77,L78_

**Source skill:** `code-review`

**Class:** confirmed

**Ref:** week1.run.jsonl L77,L78

**Source project:** a_bgt_rsi

**Evidence:** A pre-push code-review caught BLOCKING finding B1 — a stale vllm_image_tag default on all 12 Day-4 records, a reproducibility regression — and grouped the rest as nits N1-N6 (applied N1/N2/N4/N5, skipped N3/N6 with reasons). Matches code-review's adversarial read, research-risk focus, and blocking/non-blocking/nit grouping.
