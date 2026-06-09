---
slug: "dec-ap-d-036-critic-flip-co-scientist-insight-empirically-tes"
type: "decision"
date: "2026-05-27"
source: "a_bgt_rsi/DECISIONS.md"
---

# D-036 — Critic-flip (Co-Scientist insight) empirically tested on three topics — no observed benefit on this evidence; binding constraint is upstream

_apparatus decision_

**Date locked.** 2026-05-27.

**Refines.** [D-035](#d-035--multi-backend-wrapper-substrate-qwen36-27b--anthropic-api-onboarded-supersedes-d-033) — the multi-backend substrate stays as-is; the specific *application* of routing the critic to a non-Gemma backend was tested and falsified for this round.

**Decision.** Do not permanently route `workers/critic_loop_v0`'s sub-agent to a non-Gemma backend on the current evidence. The infrastructure (env-driven `CRITIC_BACKEND`, `vllm-qwen` registered, SubAgent's `reasoning_content` fallback, UI divergence-chip) all stays — it works and is available the moment empirical evidence justifies turning it on. But for these three topics, on this retrieval, the Co-Scientist insight produced *no* divergent verdicts. The binding constraint is upstream of the critic.

**The test.**

Pre-committed rule (from `human/sessions/2026-05-27.md`'s Phase-3 plan):
> *flip-critic-if: Critic returns 'survives' on Topic 2 (rediscovery probe) without surfacing KMR/Young or equivalent risk-dominance literature, OR returns 'survives' on Topic 3 (the deliberately wrong claim). Either failure alone is enough — both is dispositive.*
> *keep-critic-if: Critic correctly flags Topic 2 as rediscovery with at least one named citation to the risk-dominance literature, AND falsifies Topic 3 with the backward-induction/unraveling argument spelled out.*

Procedure: ran each topic twice — once with Gemma critic (Phase 2 baseline), once with `CRITIC_BACKEND=vllm-qwen` (Qwen3.6-27B NVFP4-MTP on :8001).

**Findings.**

| Topic | Gemma critic | Qwen critic | Same verdict? |
|---|---|---|---|
| 1 — open / Bayesian PGG (iter-004 vs iter-009) | `novel/survives` | `novel/survives`, 59.3 s, 2 turns | yes — identical conclusion, slightly more specific rationale on Qwen ("doesn't address conditional cooperation, Bayesian belief updating under noisy observations") |
| 2 — rediscovery probe (iter-002 vs iter-007) | `novel/survives`, 4.1 s | `novel/survives`, 52.6 s, 2 turns | yes — identical conclusion, Qwen named Osborne & Rubinstein explicitly |
| 3 — deliberately-wrong PD claim (iter-003 vs iter-008) | `rediscovery/survives` (Gemma critic; novelty also `rediscovery`) | substrate failed: `schema_mismatch` → critic_loop_v0 fallback `survives` — but **novelty classified `nonsense` AND Nara's summary engaged with backward induction explicitly**. The chain caught the deliberate wrongness; the critic step didn't get to. | inconclusive at the critic step; chain-as-a-whole correct |

**Cost observed.** Qwen critic ran 12–30× slower (Gemma 2–4 s, Qwen 50–60 s) and produced a `schema_mismatch` substrate failure on 1/3 runs even with the `reasoning_content` fallback in place (intermittent Qwen reasoning-placement variance).

**Diagnosis of why both critics agreed.** Both critics follow the same contract: *"Do NOT invoke knowledge from outside the retrieved set."* In all three topics, the retrieved set was Osborne & Rubinstein foundational chunks that don't cover the specialized claims at hand. Both critics correctly reported "the retrieved literature does not contain results that would falsify this." That's the *correct* behavior given the contract — not "marking own homework". The Co-Scientist insight assumed the critic was the bottleneck; for this evidence, it isn't.

**Binding constraints actually surfaced.**

- **Retrieval gap** (Topic 2). KMR 1993 / Young 1993 / Ellison 1993 / Blume 1995 are not in Chroma's foundational layer. A coordination-games-on-networks topic that asks about risk dominance can't get a rediscovery verdict when the rediscovery literature isn't retrievable. **Fix: Track B retrieval expansion** (the next slice).
- **Hypothesize selection bias** (Topic 1). The worker generated three candidates; candidate #2 contained the exact asymmetric-updating mechanism the user was probing for ("inflating the posterior probability of 'defector' types"). The worker selected candidate #1 — the most generic restatement. **Fix: prompt tightening to prefer mechanism-engaged candidates over linguistic restatements.**
- **Hypothesize claim sanitization** (Topic 3). The deliberately-wrong claim was rewritten before the critic ever saw it (verb flipped, inequality flipped). **Fix: an `as-stated` mode that bypasses the rewrite when the user signals "test this claim verbatim".**

**Reopen conditions.** D-036 falsifies critic-flip *on the current evidence*. The flip reopens cleanly if/when:

1. **Retrieval cooperates AND hypothesize preserves the claim AND the critic still parrots / fails to push back.** That's the actual "marks own homework" failure mode the Co-Scientist insight targets. It hasn't been observed.
2. **A workload arises where the critic's contract has to invoke outside knowledge.** Today the contract is "only retrieved literature"; if we widen it (e.g., let the critic call `query_chroma` more aggressively or invoke a broader knowledge base), a different-model critic might surface different judgments.
3. **The hypothesize and retrieval fixes (Track B + prompt tightening) land, three more iterations run, AND a critic-marks-own-homework pattern emerges in the cleaner data.**

**What stays in the apparatus.**

- `vllm-qwen` backend registration in `agent_wrapper/wrapper.py`.
- `CRITIC_BACKEND` env var read in `workers/critic_loop_v0.py`.
- `SubAgent` `reasoning_content` fallback for Qwen-class reasoning models (`orchestrator/subagent.py`).
- UI divergence chip wiring (sky-accented subagent chip in `ActiveIterationPanel`).
- The `vllm-qwen` container itself (port 8001) — keep running. Coder-tier workloads (Phase 2+) will use it; substrate is ready.

**What does NOT change.**

- D-035's multi-backend substrate stands. The infrastructure was the right investment regardless of this specific Co-Scientist application.
- The novelty classifier's same-model risk (per ARCHITECTURE.md §6 step 6) is unchanged. D-033's human-sampling mitigation remains the durable mitigation for novelty scoring.
- Anthropic backend stays wired; can be used for the planner tier when actually-hard planning shows up.

**Pointers.**

- `human/sessions/2026-05-27.md` § Phase-2 / Phase-3 (when written) — full session-level narrative.
- `journal/iterations/{012..020}.md` — the iteration journals on disk.
- `memory/loop_memory.jsonl` — structured iteration_records; gitignored.
- `iter-2026-05-27-002` / `-003` / `-004` (Gemma critic) and `-007` / `-008` / `-009` (Qwen critic) — the comparison pairs.

**Process note.** This entry is itself an example of what research_program_v2 § "Public research journal as primary data" asks for: a *negative* result honestly documented. The Co-Scientist insight wasn't wrong in principle; it just isn't the failure mode this slice surfaced. Falsifying it cheaply ($0, ~3 hours of work) before building elaborate planner-tier infrastructure around it is the apparatus working as designed.
