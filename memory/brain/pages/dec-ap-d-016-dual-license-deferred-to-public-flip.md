---
slug: "dec-ap-d-016-dual-license-deferred-to-public-flip"
type: "decision"
source: "a_bgt_rsi/DECISIONS.md"
---

# D-016 — Dual-license deferred to public flip

_apparatus decision_

**Date locked.** May 2026.
**Decision.** Do not stage `LICENSE` (Apache-2.0), `LICENSE-CONTENT`
(CC-BY-4.0), `CITATION.cff`, or polished `README.md` until just before
the repo flips public (Day 7+).
**Alternatives.**
- Add them now.
- Defer indefinitely.
**Rationale.** While the repo is private, license files have no force.
Staging them now invites premature decisions about the exact CC-BY
variant, the citation block formatting, etc. Better to make those
decisions once and correctly, at the moment the public flip is
imminent, with the actual artifact list in hand.
**Reversibility.** Easy; just add the files when ready.

---
