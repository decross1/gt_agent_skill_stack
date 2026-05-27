---
slug: "skill-brain-recall"
type: "skill"
source: ".agents/skills/brain-recall/SKILL.md"
---

# brain-recall — Layer B / brain

_dev-time_

**Layer:** B

**Pack:** brain

**Runtime safety:** dev-time

**Description:** Query the brain for top-N relevant entries to ground a task in prior corrections, anomalies, and decisions. Use at task start when corrections/lineage matter — bounded by recency × scope × token cap. Read-only. Dev-time only; never inherited into an apparatus-runtime skill set.
