---
slug: "hypothesis-day4-tool-call-rate"
type: "hypothesis"
date: "2026-05-20"
source: "memory/brain/narratives.jsonl"
---

# Hypothesis — LLM tool-call invocation rate floor 0.8

**Intent:** The LLM (Gemma 4 26B MoE) will fail to invoke the get_payoff_matrix tool on some non-trivial fraction of game-theoretic queries — answering from its prior memory of payoff matrices instead. Plan-stated floor for the metric `tool_call_invocation_rate` is 0.80.

**Did:** Drove the planned floor in plan.yaml day4 validation; passed if observed ≥ 0.80.

**Observed:** open — to be tested by the Day 4 end-to-end experiment.

**Would do differently:** n/a

## Referenced by

- `experiment-day4-tool-call-rate` (experiment) — **derived_from**
- `anomaly-tool-call-100pct` (anomaly) — **falsified_by**
- `agent-claude-code-main` (agent) — **authored**
