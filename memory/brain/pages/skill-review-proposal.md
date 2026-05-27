---
slug: "skill-review-proposal"
type: "skill"
source: ".agents/skills/review-proposal/SKILL.md"
---

# review-proposal — Layer B / brain

_dev-time_

**Layer:** B

**Pack:** brain

**Runtime safety:** dev-time

**Description:** Evaluate a [[propose]]'d proposal against active rules and route it to accept, reject, or human-review. Use when there are `open` entries in `memory/brain/proposals.jsonl`. Auto-rejects rule violations; auto-accepts trivial brain-content edits; everything else goes to human review.
