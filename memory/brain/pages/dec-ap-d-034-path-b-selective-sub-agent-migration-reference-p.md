---
slug: "dec-ap-d-034-path-b-selective-sub-agent-migration-reference-p"
type: "decision"
date: "2026-05-26"
source: "a_bgt_rsi/DECISIONS.md"
---

# D-034 — Path-B selective sub-agent migration; reference-passing is the next architectural fix

_apparatus decision_

**Date locked.** 2026-05-26.

**Decision.** LOOP_V0 workers migrate from Path A (one-shot Nara
tool_call) to Path B (bounded multi-turn sub-agent) **selectively,
per worker, when a concrete failure mode justifies it** — not chain-
wide. The mechanism is `orchestrator/subagent.py`, which exposes
`run_subagent(name, *, system_prompt, user_prompt,
expected_output_schema, tools, tool_dispatch, budget,
parent_request_id, ...) → SubAgentResult` (additional keyword-only
args for `log_path` and `model`; see source for the full signature)
with hard caps on turns / wall-seconds / tokens and JSON-schema
validation on output. Workers keep an **identical input/output
contract** across paths so callers don't change when a worker
migrates.

Currently migrated: `workers/critic_loop_v0` (default budget 6 turns
/ 90s; optional `query_chroma` tool; observability fields
`subagent_turns_used`, `subagent_wall_seconds`, `subagent_status`).
Still on Path A: `hypothesize`, `retrieve_literature`,
`novelty_classify`, `journal_writer`.

**Companion decision: reference-passing is the next architectural
priority.** Even with the Gemma inline-tool-call fallback parser
(`agent_wrapper/gemma_tool_parse.py`, 20 unit tests including the
real iter-010 leak sample), the LOOP_V0 chain truncates at the
`max_tokens=1024` cap because Nara copies the full `neighbors` array
through every downstream tool_call's args. The fix: workers fetch
heavy payloads by `iteration_id` from `run_state/iteration_cache/
<iteration_id>/` instead of receiving them in args. Downstream tool
schemas accept `iteration_id` (required) plus only the new fields
each step computes. Nara's prompt is rewritten to forbid re-emitting
captured payloads. `journal_writer` gathers everything from cache at
the end. See [`LOOP_V0.md`](LOOP_V0.md) §"Reference-passing".

**Alternatives considered.**

- *Wholesale sub-agent migration of all five workers.* Rejected:
  over-engineering for the cheap steps. One-shot calls are correct
  for `hypothesize` (single-turn generation), `retrieve_literature`
  (deterministic tool wrapper), `journal_writer` (deterministic
  serializer). Multi-turn would only add latency and token cost
  without changing output quality.
- *Forked Claude Code worktrees as workers.* Rejected for LOOP_V0:
  the substrate-swappable runtime keeps the option open for later,
  but in-process sub-agents are the right primitive for the
  literature-only slice. The cost ceiling, observability, and
  determinism trade-offs all favor in-process.
- *Raise max_tokens above 1024 instead of reference-passing.*
  Rejected: addresses symptom, not cause. Long inline tool_call
  emissions are parser-fragile regardless of cap, and re-emitting
  captured state through args is duplicate-state by construction.
  Reference-passing fixes both the truncation and the fragility at
  once.
- *Migrate off OpenAI tool_calls entirely (custom message protocol).*
  Deferred. The Gemma parser bridges today's stochastic format
  mismatch; a protocol change would compound the migration risk
  while LOOP_V0 is mid-build. Revisit if vLLM upgrade or runtime
  swap (NemoClawRuntime) makes the parser unnecessary.

**Rationale.**

- *Selective migration preserves the per-worker contract.* Outer
  callers (Nara, downstream workers) are agnostic to whether a worker
  is Path A or Path B. Migration is local; rollback is local.
- *SubAgent is runtime-agnostic.* The wrapper call inside
  `run_subagent` goes through PyRuntime today; a future
  NemoClawRuntime swap is mechanical.
- *Reference-passing is the load-bearing prerequisite for real
  iterations.* Without it, the chain truncates probabilistically on
  any iteration whose retrieved neighbors are non-trivial. With it,
  the chain becomes deterministic at the substrate level — Gemma's
  format-choice stochasticity stops mattering at scale.
- *The Path-B primitive unblocks fan-in/fan-out.* Future Nara →
  multiple sub-agents (e.g., three critics from different angles) →
  merged result depends on having `run_subagent` as a primitive.
  Building it now for one worker is the cheapest path to that
  future shape.

**What would reverse this.**

- A worker stays on Path A unless multi-turn reasoning is justified
  by a concrete failure mode observed on real iterations. If
  `critic_loop_v0` is consistently single-turn in practice, the
  migration is reverted and the SubAgent primitive is reserved for
  workers that actually need it.
- If reference-passing turns out to introduce more state-management
  complexity than it removes — e.g., cache lifecycle bugs, race
  conditions across UI polling, schema drift between cache files and
  iteration_record — the alternative is back to direct args with a
  raised token cap and tighter neighbor-payload trimming at the
  `retrieve_literature` boundary (return summaries, not full
  chunk_text, for downstream steps).

**Cross-refs.** D-030 (single-primary session model — Path B
sub-agents are in-process, not concurrent sessions). LOOP_V0.md
§"Path B" + §"Reference-passing". The Gemma parser is documented in
`agent_wrapper/gemma_tool_parse.py` module docstring; the chain
re-prompt mechanism is in `orchestrator/nara.py`.
