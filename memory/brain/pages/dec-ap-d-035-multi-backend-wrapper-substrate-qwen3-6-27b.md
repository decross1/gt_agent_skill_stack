---
slug: "dec-ap-d-035-multi-backend-wrapper-substrate-qwen3-6-27b"
type: "decision"
date: "2026-05-26"
source: "a_bgt_rsi/DECISIONS.md"
---

# D-035 — Multi-backend wrapper substrate; Qwen3.6-27B + Anthropic API onboarded; supersedes D-033

_apparatus decision_

**Date locked.** 2026-05-26.

**Supersedes.** [D-033](#d-033--exclude-qwen-36-entirely-the-apparatus-stays-single-model-on-gemma-4) — the single-model commitment to Gemma 4 is replaced by a tiered, multi-backend apparatus. D-033's same-model novelty mitigation framing is also reconsidered: the Google Co-Scientist paper finding that running the critic on a different model is a load-bearing insight (not a nice-to-have) is the empirical reason to admit a second and third model.

**Decision.** The wrapper becomes backend-pluggable. `agent_wrapper.backends`
exposes a `Backend` protocol; three backends register at module load:

- **`vllm-gemma`** — the existing vllm-served Gemma 4 26B-A4B-NVFP4 path.
  Default. Reads `wrapper._sync_client` / `wrapper._async_client` lazily
  at call time so the ~30 existing `patch.object(W, "_sync_client", …)`
  mocks across the test suite continue to work unchanged.
- **`ollama-coder`** — Qwen3.6-27B dense (Apache 2.0) on Ollama's
  OpenAI-compatible endpoint at `:11434/v1`. Pulled today at Q4_K_M
  (17 GB on disk, ID `a50eda8ed977`). Picked over Qwen3-Coder-30B-A3B
  (MoE), Codestral 25.01 (non-commercial license + 42% SWE-bench vs
  Qwen's 77.2%), and DeepSeek-R1-Distill-Qwen-32B (no published
  SWE-bench Verified). Caveat: the 77.2% number uses Qwen's own bash +
  file-edit scaffold; third-party reproductions are limited as of
  2026-04-23. Coder tier.
- **`anthropic`** — Claude API (default `claude-opus-4-7`) with prompt
  caching on the system message and tool definitions. Anthropic SDK
  0.104.1 installed into `.venv-chroma`. Planner tier — invoked
  selectively for hard / complex orchestration, never as the
  per-iteration default (the apparatus stays self-hosted by default).

The substrate is **additive**: every existing call site defaults to
`vllm-gemma`, no behavior change. Backend selection is opt-in via a
`backend=` kwarg on `call_sync` / `call_async` / `call_with_tools`
(wrapper), `run_subagent` (sub-agent primitive), and `run_iteration`
(Nara). The `calls.jsonl` schema's `host_metadata` is relaxed to allow
heterogeneous per-backend shapes (existing fields remain valid; new
`backend` discriminator added as optional).

**Routing model (today vs deferred).**

- **Today**: declarative — callers (workers, sub-agent dispatchers,
  Nara) opt into a backend at the call site. No automatic routing.
  Coder workloads pass `backend="ollama-coder"`; planning workloads
  pass `backend="anthropic"`.
- **Deferred to follow-up slices** (still under the D-035 umbrella):
  (1) optional `default_model` / `model_tier` field on each tool spec
  so the runtime can route mechanically rather than each call site
  hardcoding the brain; (2) a complexity-calculator stub with a
  threshold-based escalation hook to the planner tier; (3) per-iteration
  override (a "this iteration is hard, use SOTA" flag). These are the
  obvious next surfaces but are explicitly out of today's scope per
  the "for now just onboard and set up" framing.

**Verification.**

- **Unit / translation tests** — 76 tests across the wrapper + backend
  registry + Anthropic translation + critic + worker + orchestrator
  paths all pass. New: `tests/test_backend_registry.py` (8 tests),
  `tests/test_anthropic_backend.py` (15 tests). Pre-existing
  `tests/test_dispatch_coding_agent.py` failures (18 errors) are
  D-030 fallout from archived `agent/ownership.yaml` — unrelated to
  this work.
- **Live smoke — ollama-coder** — blocked. The vllm-gemma4 container
  is holding ~110 GiB of 128 GiB unified memory; Qwen3.6-27B at
  Q4_K_M requires ~36 GiB at inference time; Ollama returns 500
  `model requires more system memory (36.0 GiB) than is available
  (12.2 GiB)`. Substrate is verified by the round-trip (correct
  request shape on the wire); cohabitation requires either a smaller
  Qwen quant, a vllm right-sizing pass, or a scheduled stop/start
  pattern. Tracked as the next-but-one follow-up.
- **Live smoke — anthropic** — blocked on `400 invalid_request_error
  — credit balance is too low`. Request shape correct; live verify
  gated on credit top-up.

**Alternatives considered.**

- *Defer multi-backend until critic-on-different-model is the
  bottleneck.* Rejected: the reference-passing refactor (D-034) and
  the multi-backend substrate both touch `wrapper.py`, `subagent.py`,
  `nara.py`. Laying the substrate first lets reference-passing land on
  a backend-aware foundation, and avoids cracking open the same files
  twice.
- *Adopt an LLM-as-router from day one.* Rejected: premature without
  evidence the static per-tool tier is wrong. Hook is in place for
  later (complexity-calculator stub is the deferred follow-up).
- *Graduate Nara itself to Claude Opus every turn.* Rejected for now:
  the apparatus design pillar is self-hosted by default; SOTA is the
  ceiling, not the floor. The substrate permits the graduation later
  with a one-line change (`run_iteration(..., backend="anthropic")`),
  but the default stays vllm-gemma.
- *Re-pull `qwen3.6:35b` to match the pre-D-033 setup.* Rejected:
  Qwen3.6-27B's SWE-bench Verified (77.2% per Qwen's blog) and
  Terminal-Bench 2.0 (59.3%) are well ahead of the older 35B sibling
  for coding-tier workloads, and the smaller footprint helps with the
  co-residency RAM problem (which is the binding constraint anyway).

**Why this is not a rollback of D-033.** D-033's commitment was to
the apparatus staying single-model on Gemma 4 *for novelty scoring* —
the same-model novelty-classify worker stays Gemma. What D-035 admits
is that *other* roles (critic, planner) benefit from a different
model. The novelty-classify worker remains on Gemma per D-033's
mitigation framing (logged human sampling per ARCHITECTURE.md §6 step
6). The critic is the worker most likely to flip first, per the
Co-Scientist insight.

**Pointers.**

- `agent_wrapper/backends/{__init__,base,vllm_openai,ollama_openai,anthropic}.py`
- `schema/calls.jsonl.schema.json` — `host_metadata` relaxed
- `tests/test_backend_registry.py`, `tests/test_anthropic_backend.py`
- Research that picked Qwen3.6-27B over the alternatives: in-session
  general-purpose agent report, 2026-05-26.
