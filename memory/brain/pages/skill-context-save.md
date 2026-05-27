---
slug: "skill-context-save"
type: "skill"
source: ".agents/skills/context-save/SKILL.md"
---

# context-save — Layer C / meta

_dev-time_

**Layer:** C

**Pack:** meta

**Runtime safety:** dev-time

**Description:** Save the current working session to durable memory before ending or switching tasks. Use when wrapping up, hitting a context limit, or pausing work — writes a handoff snapshot so the next session resumes without re-deriving everything.
