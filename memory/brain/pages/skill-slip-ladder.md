---
slug: "skill-slip-ladder"
type: "skill"
source: ".agents/skills/slip-ladder/SKILL.md"
---

# slip-ladder — Layer B / core

_dev-time_

**Layer:** B

**Pack:** core

**Runtime safety:** dev-time

**Description:** Declare a bounded sequence of deadline extensions when a task is on the right approach but not finishing inside its time budget. Use when [[fallback]] does not fit because there is no alternative approach to switch to — only "more time, same approach, with a stated cap". Each slip is logged; the cap is real; resolution criterion is declared upfront.

## Referenced by

- `proposal-p-003` (proposal) — **targets**
