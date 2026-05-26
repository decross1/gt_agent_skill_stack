---
slug: "experiment-day4-tool-call-rate"
type: "experiment"
date: "2026-05-20"
source: "memory/brain/narratives.jsonl"
edges:
  - {type: derived_from, dst: "hypothesis-day4-tool-call-rate", dst_type: "hypothesis"}
  - {type: produced, dst: "anomaly-tool-call-100pct", dst_type: "anomaly"}
---

# Experiment — Day 4 end-to-end tool-call invocation rate

**Intent:** Measure tool_call_invocation_rate against the planned floor 0.80 via end-to-end calls through the vLLM (Gemma 4 26B) → tool-loop wrapper. Same prompt set, deterministic temperature.

**Did:** Ran the e2e tool-call chain test (caller_tag=test_tool_call_e2e); logs at a_bgt_rsi/logs/day4_e2e.jsonl. Each chain: system prompt mandating tool use → user query → optional tool call → optional follow-up turn.

**Observed:** tool_call_invocation_rate = 1.00 across the test set. No bypasses observed in either e2e or robustness variant.

**Would do differently:** None on the run itself. The metric is higher than the floor — see anomaly-tool-call-100pct for interpretation.

## Links

- **derived_from** → `hypothesis-day4-tool-call-rate` (hypothesis)
- **produced** → `anomaly-tool-call-100pct` (anomaly)
