---
slug: "anomaly-tool-call-100pct"
type: "anomaly"
date: "2026-05-20"
source: "memory/brain/narratives.jsonl"
edges:
  - {type: falsified_by, dst: "hypothesis-day4-tool-call-rate", dst_type: "hypothesis"}
  - {type: linked_to, dst: "dec-fw-2026-05-24-treat-100-metrics-in-small-n", dst_type: "correction"}
---

# Anomaly — tool-call invocation at 100%

**Intent:** Planned floor was 0.80, expecting a non-trivial fraction of bypasses. Observed 1.00.

**Did:** Inspected the e2e logs; confirmed the model emitted the tool-call on every prompt; confirmed the system prompt is highly directive (`You MUST call the get_payoff_matrix tool ... do not state any payoff numbers from memory`).

**Observed:** 100% rate likely reflects the directive system prompt, not robust tool-using behavior under weaker prompts. A small-N test with a strong prompt is structurally biased upward — a clean-looking result that does not generalize.

**Would do differently:** Repeat with a softer prompt + a larger N before treating tool-use as robust. Flag any future 100% metric on a small N as suspicious-clean.

**Corrections honored:** fw-correction-suspicious-clean-100pct-2026-05-24

## Links

- **falsified_by** → `hypothesis-day4-tool-call-rate` (hypothesis)
- **linked_to** → `dec-fw-2026-05-24-treat-100-metrics-in-small-n` (correction)

## Referenced by

- `experiment-day4-tool-call-rate` (experiment) — **produced**
- `dec-fw-2026-05-24-treat-100-metrics-in-small-n` (correction) — **references**
- `agent-claude-code-main` (agent) — **authored**
