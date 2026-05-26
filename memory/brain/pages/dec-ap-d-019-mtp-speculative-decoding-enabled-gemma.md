---
slug: "dec-ap-d-019-mtp-speculative-decoding-enabled-gemma"
type: "decision"
date: "2026-05-18"
source: "a_bgt_rsi/DECISIONS.md"
---

# D-019 — MTP speculative decoding enabled (Gemma 4 + official drafter)

_apparatus decision_

**Date locked.** 2026-05-18, after the post-2026-05-05 MTP research
review; human-approved. Resolves the "MTP support" open decision.
**Decision.** Enable MTP (Multi-Token Prediction) speculative decoding on
the vLLM Gemma 4 stack, using the official Google drafter
`google/gemma-4-26B-A4B-it-assistant` (~870 MB BF16) paired with the
`nvidia/Gemma-4-26B-A4B-NVFP4` IT target. The Day-1 launch adds
`--speculative-config '{"method":"mtp","model":".../gemma-4-26b-a4b-it-assistant","num_speculative_tokens":4}'`.
**Alternatives.**
- No MTP — NVFP4 baseline, ~52 tok/s single-stream.
- FP8 + MTP — ~108 tok/s, faster, but re-pins the whole model stack.
- GGUF / Ollama — rejected: no MTP path, no concurrency, slower.
**Rationale.** MTP is a ~1.84× single-stream speedup on GB10 with zero
quality loss (the target verifies every accepted token), validated by
community benchmarks. NVFP4 (not FP8) is retained because an FP8 swap
would re-derive every MARLIN / startup-log / image-tag pin for a ~12 %
delta that changes no per-day budget. The drafter MUST pair with the IT
target — pairing with a base target is a 38 % slowdown.
**Operational caveats.** The preview vLLM image's bundled `gemma4_mtp.py`
has two bugs on quantized targets (`intermediate_size` read from the
wrong config layer; `quant_config` wrongly propagated to the BF16
drafter); the head of vLLM PR #41745 fixes both. Until the image is
rebuilt, bind-mount the patched file (`infra/vllm_patches/gemma4_mtp.py`).
The Day-1 tok/s band is updated to 80–130 with MTP γ=4; the hard floor
stays 40.
**Reversibility.** Easy — drop the `--speculative-config` flag and the
drafter mount to fall back to the NVFP4 baseline.
**Plan impact.** `plan.yaml` updated 2026-05-18 (6 edits: weights size
note, drafter pinned, `day1_block2_vllm_serve` launch + validation, tok/s
band, Appendix C, `infra/bookmarks.txt`).

**2026-05-18 update — DEFERRED, not abandoned.** Day-1 execution found
the then-pinned image (`:gemma4-cu130`, vLLM 0.19.1.dev6) could not run
MTP: it predates merged vLLM PR #41745 (9 files of MTP support, not just
`gemma4_mtp.py`) and crashed in `SpeculativeConfig` on the unrecognized
`gemma4_assistant` drafter. Per human decision, MTP is deferred to
Week 2+ — get the baseline product working first. The `plan.yaml` task
#6/#7 MTP edits were reverted (tok/s band back to [50,110]). The drafter
weights and `infra/vllm_patches/gemma4_mtp.py` remain staged. Whether
the re-pinned v0.20.0 image (D-020) ships PR #41745 is untested; MTP
re-evaluation is re-tracked under "Open decisions" below.

**2026-05-19 update — ENABLED (see D-022).** The re-pinned v0.20.0
image was tested and found NOT to ship PR #41745 (no `gemma4_mtp.py`,
no `Gemma4MTPModel` registry entry). Re-pinning to v0.21.0 — the first
vLLM release that includes #41745 — enabled MTP cleanly: single-stream
decode 32.21 → 69.44 tok/s, and the day_2 50-call sweep now passes all
5 checks. The deferral is closed.

---
