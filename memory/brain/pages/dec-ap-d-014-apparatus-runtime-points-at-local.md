---
slug: "dec-ap-d-014-apparatus-runtime-points-at-local"
type: "decision"
source: "a_bgt_rsi/DECISIONS.md"
---

# D-014 — Apparatus runtime points at local Gemma 4, never at Claude

_apparatus decision_

**Date locked.** May 2026 (Anthropic policy April–May 2026).
**Decision.** Pi and OpenClaw point at the *local* Gemma 4 vLLM endpoint
on `localhost:8000`. They never authenticate to a Claude subscription.
Claude Code (first-party Anthropic) authenticates to Max separately and
is used for the apparatus's *bootstrap* work (Day 1–7 setup, debugging)
under human supervision — distinct from the apparatus's runtime.
**Alternatives.**
- Point OpenClaw at the Claude API via the Anthropic-issued Agent SDK
  credit.
- Use Claude Code as the apparatus's runtime orchestrator.
**Rationale.** Three reasons. (1) The apparatus's central claim is that
a single researcher can build and operate a useful research loop on
*open* models with *local* compute. Routing the orchestrator through
Anthropic invalidates that claim. (2) Anthropic's June 15, 2026 policy
caps third-party Agent SDK usage on Max-20x at $200/month of API
list-rate tokens, non-rolling, which would consume the budget
unsustainably for a continuous research loop. (3) Local compute is the
data-sovereignty guarantee — every prompt is a research observation; the
apparatus needs that data to stay local.
**Reversibility.** Conceptually possible but reverses the project's
identity. Not a swap, a different program.

---
