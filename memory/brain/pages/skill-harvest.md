---
slug: "skill-harvest"
type: "skill"
source: ".agents/skills/harvest/SKILL.md"
---

# harvest — Layer C / meta

_dev-time_

**Layer:** C

**Pack:** meta

**Runtime safety:** dev-time

**Description:** Harvest feedback for the framework's own skills from a consumer project's execution trace. Use once per consumer work session — reads the consumer's run log, git history, and decision log since a stored watermark, classifies each finding against the skill it bears on, and appends to the feedback ledger. Read-only on the consumer.
