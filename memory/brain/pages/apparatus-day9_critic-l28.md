---
slug: "apparatus-day9_critic-l28"
type: "llm_call"
date: "2026-05-25"
source: "day9_critic.jsonl:28"
---

# a_bgt_rsi: Critic — day9_critic L28

_Hypothesis:
Switching from the v0.20.0 vLLM serving image to v0.21.0 increased tool-call invocation rate from 0.78 to 1.00 on the Day-4 sweep. We attribute this to the v0.21.0 changes to the tool-calling parser.

Experimental context:
Day-1…_

**Did:** **Confounding Variables:** The hypothesis attributes the change exclusively to the tool-calling parser, yet the experimental context reveals concurrent changes to the image, prompt, backend, and `max_tokens` parameters. Because these variables were not held constant, it is impossible to isolate the …

**Observed:** latency=3752ms tokens_in=316 tokens_out=174 model=gemma-4-26b-a4b
