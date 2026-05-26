---
slug: "dec-ap-d-009-autoresearch-fork-use-canonical-karpathy-autores"
type: "decision"
source: "a_bgt_rsi/DECISIONS.md"
---

# D-009 — Autoresearch fork: use canonical karpathy/autoresearch

_apparatus decision_

**Date locked.** May 2026 (corrected from earlier reference to a fork).
**Decision.** Clone `github.com/karpathy/autoresearch` (canonical
upstream). Do NOT use `matt-langston/autoresearch`.
**Alternatives.**
- `matt-langston/autoresearch` — a fork tuned for a *dual*-GB10 Spark
  bundle.
**Rationale.** The matt-langston fork carries configuration assumptions
that mismatch a single-Spark setup (the apparatus's hardware reality).
Earlier planning conversations imprecisely pointed at the fork; the
canonical upstream is the correct dependency.
**Operational scope.** Autoresearch is a Week-2+ tool; Week 1 only needs
the directory present. It fires on the ~10–20 % of loop cycles where the
agent identifies a pattern that a specialist model could capture better
than general reasoning.
**Reversibility.** Trivial. `git clone` from the right URL.

---
