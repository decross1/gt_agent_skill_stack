---
slug: "dec-ap-d-033-exclude-qwen-3-6-entirely-the"
type: "decision"
date: "2026-05-26"
source: "a_bgt_rsi/DECISIONS.md"
---

# D-033 — Exclude Qwen 3.6 entirely; the apparatus stays single-model on Gemma 4

_apparatus decision_

**Date locked.** 2026-05-26.

**Decision.** Drop Qwen 3.6 27B Dense as a planned second model.
The apparatus runs single-model on Gemma 4 26B-A4B-NVFP4 indefinitely.
Per-user direction: keep the machine clean — one orchestrator model,
one embedding model, one substrate. No Qwen weights are pulled, no
`/mnt/models/qwen-*` directories are created, no Qwen-related docker
images are added.

**Alternatives.**

1. Pull Qwen weights now per the prior D-006 plan (Week 2-3 swap).
   Rejected: not needed for LOOP_V0 or Part 2; adds ~30-50 GB and
   substrate complexity (a second served model, routing decisions,
   per-model metric tracking).
2. Leave Qwen "deferred" per the prior plan. Rejected: deferring
   indefinitely is functionally exclusion; calling it that
   honestly tells future-me what to expect.
3. The chosen path: explicit exclusion, with a documented reopen
   condition.

**Rationale.**

- **No Qwen on disk.** `/mnt/models/` has only `bge-m3`,
  `gemma-4-26b-a4b-nvfp4` (active), and the unused
  `gemma-4-26b-a4b-it-assistant` (also being removed). Qwen was
  planned but never installed.
- **The Phase-2 reason for a second model was Elo circularity in
  novelty scoring** (ARCHITECTURE.md §6 step 6: same-model novelty
  grading lets the model surface results from its own embedding /
  output space). The Phase-1 mitigation — logged human-sample rate
  on automated novelty calls — is sufficient when the human is in
  the loop for every iteration, which is LOOP_V0's design.
- **Single-substrate simplifies operations.** One served model means
  one vLLM container, one config, one set of perf measurements, one
  fail-mode-canary, one model-version stamp on every record. The
  Phase-1 design (D-012, D-007) explicitly excluded the dual-model
  routing layer for similar reasons; D-033 extends that posture to
  "no second model at all."
- **Reversibility is preserved.** If a specific bottleneck emerges
  later (Gemma 4 demonstrably fails some class of task that an
  alternative model handles), the swap pattern is a vLLM container
  restart with different weights — minutes of work, not weeks.
  Starting from a clean "no second model" baseline and adding one
  if needed is cheaper than maintaining a "second model is planned
  but not built" hypothetical.

**What this DOES NOT change.**

- Gemma 4 26B-A4B-NVFP4 remains the inviolate-pinned orchestrator
  (CLAUDE.md rule 2 unchanged).
- The Elo-circularity risk on novelty scoring remains real (see
  ARCHITECTURE.md §6 step 6); the Phase-1 mitigation (logged human
  sample rate) becomes the *durable* mitigation, not a temporary
  one until a second model lands.
- D-006 (defer Qwen 3.6 to Week 2-3) is superseded by this entry.
- D-012 (dual-model routing excluded) is reinforced, not changed.

**What would reverse this.** (1) Gemma 4 demonstrably fails a
specific, narrow task class — measured against a known benchmark,
reproducibly, with the failure attributable to model quality rather
than prompt or retrieval. (2) A novelty-evaluation second-opinion
need that human sampling cannot cover — e.g., overnight autoresearch
loops where the human cannot review every call. (3) Compute budget
expands such that running two served models concurrently is no
longer a cost trade-off.

**`gemma-4-26b-a4b-it-assistant` is RETAINED** (832 MB at
`/mnt/models/`). It is *not* unused — the running vLLM container
loads it as the **MTP speculative-decoding draft model** per D-022's
launch args (`--speculative-config '{"method":"mtp","model":
"/models/gemma-4-26b-a4b-it-assistant","num_speculative_tokens":4}'`).
Removing it breaks vLLM on next restart and gives up the ~52 tok/s
single-stream baseline (D-022's whole point). It is referenced by
`setup/day2_vllm_serve_mtp.sh` and `setup/day4_vllm_serve_tools.sh`.

*Process note.* An earlier draft of this decision claimed
it-assistant was unused and removed it; that removal was reverted
~10 minutes later when the dependency was discovered. The lesson:
"check what running containers actually mount before removing
anything under `/mnt/models/`."

**Supersedes.** D-006 (Defer Qwen 3.6 to Week 2-3). D-006 stays in
the log as history; D-033 is the active position.
