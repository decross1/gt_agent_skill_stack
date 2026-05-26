---
slug: "dec-ap-d-021-day-1-decode-throughput-is-memory-bandwidth-boun"
type: "decision"
date: "2026-05-18"
source: "a_bgt_rsi/DECISIONS.md"
---

# D-021 — Day-1 decode throughput is memory-bandwidth-bound on GB10

_apparatus decision_

**Date locked.** 2026-05-18, Day-1 follow-up investigation + the E1
clock experiment (`notes/day1-bench-debug.md`).
**Decision.** Settled by investigation and the E1 experiment:
1. `scripts/bench_tokens_per_sec.py` is corrected to measure *true*
   decode rate — streaming, first/last-token timestamps, TTFT split,
   warmup discard, `/metrics` cross-check. The prior version reported
   end-to-end throughput mislabelled as "decode tok/s".
2. Single-stream decode (~32.4 tok/s) is **memory-bandwidth-bound** —
   bound by reading the model weights from unified LPDDR5X every token.
   It is not compute/clock-bound, not thermally limited, and not gated
   by KV-cache traffic.
3. The 32-vs-~52 gap is a tuning target in the *memory path*, not a GPU
   clock or power-profile issue. The Day-1 baseline number stands
   (human decision, run log 06:15Z).
**Alternatives considered.** (a) "Compute-bound, lift the clock" —
tested as E1 and **rejected**: see Evidence. (b) Accept 32 tok/s as a
structural ceiling — rejected: E6/E7 are open memory-path levers.
**Evidence.** E1 experiment (2026-05-18): locking the GPU clock
(`nvidia-smi -lgc 3003`) raised it from 2411→~2560 MHz under load and
power from 28→38 W, but decode tok/s did **not** change (32.4→32.46).
A ~6 % clock rise yielding 0 % throughput rules out a compute/clock
bound — the 96 % SM utilisation seen earlier was warps stalled on
memory, not saturating arithmetic (SM util does not distinguish the
two). The E2 context-length sweep showed decode nearly flat (32.3 @
256-ctx → 31.6 @ 2816-ctx), so KV-cache traffic is not the bottleneck
either — the per-token cost is the weight read (BF16 dense + 4-bit MoE
experts). On GB10 (SM12x, no native FP4 — D-018) vLLM runs the Marlin
weight-only FP4 path; achieved effective bandwidth sits well below the
273 GB/s nominal.
**Implication.** Clock and power-profile levers are dead (E1 FAIL). The
throughput levers are **E7** (MTP / speculative decoding — reads the
weights once per K tokens, the right lever for a weight-bandwidth-bound
decode) and **E6** (a faster FP4 MoE kernel with a better memory-access
pattern). Experiment plan in `notes/day1-bench-debug.md`.
**Supersedes.** The D-002 calibration (~50–52 tok/s) is qualitatively
consistent (memory-bound) but its specific number does not transfer to
this checkpoint + vLLM 0.20.0 + Marlin FP4; treat ~32 tok/s as the
measured GB10 baseline pending E6/E7.
**Reversibility.** N/A — a measurement correction and a hardware
finding, not a chosen direction.

---
