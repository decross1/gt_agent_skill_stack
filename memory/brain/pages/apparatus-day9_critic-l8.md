---
slug: "apparatus-day9_critic-l8"
type: "llm_call"
date: "2026-05-25"
source: "day9_critic.jsonl:8"
---

# a_bgt_rsi: Critic — day9_critic L8

_Hypothesis:
Switching from the v0.20.0 vLLM serving image to v0.21.0 increased tool-call invocation rate from 0.78 to 1.00 on the Day-4 sweep. We attribute this to the v0.21.0 changes to the tool-calling parser.

Experimental context:
Day-1…_

**Did:** **Confounding Variables:** The hypothesis attributes the change exclusively to the tool-calling parser, but the experimental context reveals concurrent changes to the image, prompt, and backend. Because these variables were not held constant, it is impossible to isolate the parser as the causal driv…

**Observed:** latency=5103ms tokens_in=316 tokens_out=272 model=gemma-4-26b-a4b
