---
slug: "dec-ap-d-031-nemoclaw-install-feasible-deferred-today"
type: "decision"
date: "2026-05-26"
source: "a_bgt_rsi/DECISIONS.md"
---

# D-031 — NemoClaw: install feasible, deferred today (sudo-blocked autonomous session)

_apparatus decision_

**Date locked.** 2026-05-26 (LOOP_V0 Part 1, primary session).

**Decision.** Do not run NemoClaw install in today's autonomous
primary session. Keep `NemoClawRuntime` as a `NotImplementedError`
stub in `orchestrator/runtime.py`. The substrate-swappable design
(D-030) holds: when NemoClaw is installed in a future session (by
the human, or interactively), implementing `NemoClawRuntime` is
mechanical and Nara does not change.

**Investigation summary** (≈10 min of the 90-min cap):

Status of NemoClaw as of 2026-05-26 (vs. Day-1's D-008 state in
March 2026):

- Now installable via a public installer:
  `curl -fsSL https://www.nvidia.com/nemoclaw.sh | bash`
  Bootstrap clones `github.com/NVIDIA/NemoClaw` and runs
  `scripts/install.sh` from the checkout.
- DGX Spark is officially supported (`spark-install.md` in repo:
  "DGX Spark needs no platform-specific pre-setup as Docker is
  pre-installed"). Per-repo `setup-spark.sh` exists.
- Repo still marked "Alpha" in `CLAUDE.md` ("Interfaces may change
  without notice"), but the install path is no longer the ad-hoc
  state described in March 2026.

Prerequisites on this host (all met):

- Docker 29.2.1 (D-022 vLLM image already running).
- Node.js 22.22.2 (≥ 20 required).
- `NVIDIA_API_KEY` set in env.
- 3.4 TB free on `/dev/nvme0n1p2`.
- User in `docker` and `sudo` groups; Docker accessible without sudo.
- GPU + CUDA 13.0 driver (`nvidia-smi` reports 580.142).

The blocker: the installer needs sudo to run
`nvidia-ctk cdi generate` for NVIDIA Container Device Interface
spec generation (per `scripts/install.sh` line 1850). The host
requires a sudo password (not passwordless). An autonomous Claude
Code session cannot type the password. The installer would prompt
and halt.

Other sudo-using paths in the installer (docker install, docker
systemd enable, docker group add) are no-ops on this host because
Docker is already installed, active, and the user is already in
the `docker` group.

**Alternatives.**

1. Push through with `NEMOCLAW_NON_INTERACTIVE_SUDO_MODE=prompt` —
   doesn't help; still requires interactive password.
2. Skip the nvidia-cdi step — installer warns and continues per
   `scripts/install.sh:1862` ("Could not obtain sudo credentials
   for NVIDIA CDI device spec generation"), but downstream behavior
   when CDI is unset is undocumented and may break GPU access from
   sandboxed agents.
3. Pre-authorize passwordless sudo for the install duration —
   security-meaningful change to the host; out of scope for a doc
   reorg + scaffolding session.
4. The human runs the installer directly outside an autonomous
   session — straightforward; works in any future working session.

**Rationale.** Today's session has scope beyond NemoClaw (Runtime
abstraction, tool registry, schemas, Nara hello-world, end-to-end
smoke). Spending the remaining ~80 minutes of the cap on sudo
workarounds risks zero-output day. The substrate-swappable design
means we do not lose architectural value by deferring: when
NemoClaw is later installed, swapping is a one-line change to the
`runtime=` argument in `nara.run_iteration()`.

**Reversibility.** Trivial. To revive NemoClaw integration in a
future session:

1. Human runs `curl -fsSL https://www.nvidia.com/nemoclaw.sh | bash`
   in a normal terminal (typing the sudo password when prompted).
2. Implement `NemoClawRuntime.dispatch_tool` to shell out to
   `nemoclaw run` or call the NemoClaw CLI's blueprint API.
3. Swap `runtime=PyRuntime()` → `runtime=NemoClawRuntime()` in CLI
   default; PyRuntime stays as fallback.

**What would reverse the deferral.** (1) The human installs
NemoClaw outside the session — the implementation is ~150 LOC
when prereqs are met. (2) Passwordless sudo is enabled in a way
the user is comfortable with. (3) The user explicitly requests an
attended-but-paused install session where they type the sudo
password mid-run.

**Supersedes.** D-008 (NemoClaw alpha discipline, plain-Docker
fallback) — partially. D-008's "re-attempt with fresh eyes at the
end of Week 1" intention is honored; the deferral reason has
shifted from "alpha and breaks" to "installable but needs sudo
interaction we don't have in this session."

**UPDATE 2026-05-26 ~03:00 UTC — install completed (attended).** The
user ran the install in a real terminal with the sudo password
available. Outcome:

- `nemoclaw v0.1.0` CLI installed (`/home/decross1/.npm-global/bin/nemoclaw`,
  symlinked to a wrapper at `/home/decross1/.local/bin/nemoclaw`).
- Sandbox `nara-sandbox` built and running
  (`openshell-nara-sandbox-763df558-...`).
- OpenClaw v2026.5.18 baked into the sandbox image (Dockerfile steps
  22-23). Gateway listening at http://127.0.0.1:18789, /health
  returns `{ok:true, status:live}`.
- Inference: vllm-local provider, model `gemma-4-26b-a4b`, routed
  through NemoClaw's egress proxy at `10.200.0.1:3128`. Sandbox-side
  status reports "Inference (vllm backend): healthy".
- Resource profile: gamer (25% CPU / 25% RAM).
- GPU passthrough verified (3 GPU proofs passed: nvidia-smi, /proc
  comm write, `cuInit(0)` via libcuda).
- Dispatch path verified: `nemoclaw nara-sandbox exec --no-tty -- echo
  "hello"` returns cleanly.

**Two artifacts to note (non-blocking):**

1. **Container Docker healthcheck reports "unhealthy"** even though
   the gateway is fine. The in-container `curl 127.0.0.1:18789/health`
   fails for an internal network-namespace reason, but the gateway is
   reachable from the host and responding. Cosmetic.

2. **`openshell sandbox connect nara-sandbox` hangs** without a TTY
   (same root cause that blocked autonomous install). This affected
   the wizard's step 7/8 ("Setting up OpenClaw inside sandbox") and
   reported a non-zero exit, but OpenClaw was already baked into the
   image at build time, so nothing material was missing. The CLI's
   `exec --no-tty` and the gateway API are the practical dispatch
   paths and both work.

**NemoClawRuntime.dispatch_tool — implementation DEFERRED.** Nara is
currently a Python orchestrator on the host that calls Python worker
functions in-process. Shelling out to the sandbox via `nemoclaw
exec` (or speaking to the gateway API) for every tool call would
add network/serialization overhead for no benefit at LOOP_V0's
current shape. NemoClawRuntime earns its keep when **Phase-2
dispatched coding agents** become real (Nara dispatches a coding
sub-agent to write a new worker → that sub-agent runs as an OpenClaw
session in the sandbox). PyRuntime remains the default and only
working runtime for LOOP_V0 hello-world iterations.

D-031 is now **partially resolved**: install side done, runtime
integration deferred to Phase-2 use cases.

---
