---
slug: "critic-emit-mlintern-nemoclaw-2026-06-09"
type: "reflection"
date: "2026-06-09"
source: "memory/brain/narratives.jsonl"
---

# critic_emit_mlintern_nemoclaw_2026-06-09

**Intent:** Fix the research-integrity bug where the autonomous loop scored an off-domain claim novel/survives; find the REAL cause of ml-intern's silent 0 papers (key rotation deferred by the human); land the UI emit prerequisites + a minimal NemoClaw host tool plane — all but the UI render — run as a Dynamic Workflow.

**Did:** Ran wf_e367ee98-045 (4 limbs + synthesis). Integrated: a retrieval-relevance gate (nara computes it; novelty/critic stamp low_confidence WITHOUT flipping, rule 4); the ml-intern query fix (keyphrase-reduce); coordinator_cycles.jsonl + health_signals + a 'coordinator' active_run identity; a host tool_plane + OpenClaw bundle + smoke runbook. Committed 0d9c4af behind the verify gate (suite 841 green + a real iteration smoke).

**Observed:** TWO sharp findings. (1) ml-intern's 0 papers was NOT the key (verified valid: a 4-term query returns 8921 hits incl. the prior art) — _distill_query fed S2 the full 39-term hypothesis and S2 keyword-AND search saturates to total=0 past ~10-12 terms. The human's instinct to defer rotation + demand deeper investigation was correct. (2) The relevance signal that separates off- from on-domain is LEXICAL overlap, NOT embedding cosine — the bug's cosine (0.60) sits inside the on-domain band, so a cosine threshold would false-positive real iterations; overlap cleanly separates (bug = single lowest of 41 rows). The smoke was instructive: re-running the FASE topic, the hypothesizer this time produced an ON-DOMAIN game-theory hypothesis, retrieval was relevant (incl. the real FASE paper 2606.09800), and the gate correctly did NOT fire (low_confidence=False) — proving it is calibrated, not a blunt instrument. The deep-research caveat held: a web summarizer mis-bound FASE to the wrong arXiv id (2606.09798=robotics) — fetch primary sources by verified id. NemoClaw: the gateway recovered (nemoclaw recover), but the sandbox->host seam is 403 (closed by default) — Limb D's earlier '200 via hostname' was stale; opening a host endpoint needs a blueprint policy + rebuild.

**Would do differently:** Build the hypothesis-grounding check (the OTHER half — the relevance gate catches an irrelevant CORPUS but not a hypothesis CONFABULATED relative to its source paper); it needs the seed abstract threaded into the iteration. Upgrade ml-intern to route (a) — query S2 by the seed paper's title/arxiv id — to sidestep a confabulated hypothesis entirely. Domain-filter the topic picker so off-domain seeds don't enter. Treat a verify-gate smoke as exploratory, not pass/fail: the planner is an LLM (it chose promote_findings on the first --execute), so a direct iteration was needed to exercise the fix.

**Corrections honored:** D-037, D-040, D-043, D-014, inviolate-rule-4, inviolate-rule-8, inviolate-rule-7

## Referenced by

- `agent-claude-code-main` (agent) — **authored**
