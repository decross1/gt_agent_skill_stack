---
slug: "dec-ap-d-004-cuda-13-0-pin-auto-update-locked"
type: "decision"
source: "a_bgt_rsi/DECISIONS.md"
---

# D-004 — CUDA 13.0 pin, auto-update locked

_apparatus decision_

**Date locked.** Day 0 of Spark setup, May 2026.
**Decision.** Pin CUDA 13.0 via `apt-mark hold` on the eight
`cuda-*-13-0` packages; disable `unattended-upgrades`; manual updates only.
**Alternatives.**
- CUDA 13.2 (current). Allow auto-update.
- Stay on CUDA 12.x.
**Rationale.** CUDA 13.2 produces gibberish output on low-bit quantized
models — a documented silent-failure mode flagged in the
validation-pass review and confirmed across multiple community reports.
The Spark ships with 13.0 working; the cost of "drifting" to 13.2 via
auto-update is unrecoverable until a known-good 13.x point release lands.
**Operational caveat.** Two `cuda-*-config-common` packages drifted to
13.2.75-1 on the Spark; characterized as cosmetic (not in runtime path).
Before any first vLLM serve, run `nvcc --version && nvidia-smi | head -3`
and confirm 13.0 in the driver line — if anything shows 13.2 in the
runtime path, back out before serving.
**Reversibility.** Mechanically easy (unhold, upgrade); operationally
gated on a verified-clean CUDA 13.x release.

---
