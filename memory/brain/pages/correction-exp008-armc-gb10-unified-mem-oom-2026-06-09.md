---
slug: "correction-exp008-armc-gb10-unified-mem-oom-2026-06-09"
type: "correction"
date: "2026-06-09"
source: "memory/brain/narratives.jsonl"
edges:
  - {type: derived_from, dst: "runlog-exp008-armc-unified-mem-freeze-incident-l1002", dst_type: "run_log_entry"}
  - {type: derived_from, dst: "runlog-exp008-first-live-run-triage-l1001", dst_type: "run_log_entry"}
---

# Correction — do not launch a 2nd large model (arm C, ~48GiB) alongside production gemma on the GB10's shared unified memory; the util cap is not enough

_apparatus correction (a_bgt_rsi exp008 / GB10 OOM)_

**Intent:** Run exp008 arm C (unquantized 26B QAT, ~48GiB) live on the DGX Spark (GB10, ~121GiB UNIFIED memory) alongside the resident production gemma :8000 (~48GiB) and qwen, to get a real QAT-vs-NVFP4 verdict (D-039).

**Did:** First live attempt OOM-crashed the :8002 arm at startup (no --gpu-memory-utilization cap -> vLLM grabbed ~90%); hardened in consumer commit 3b53380 by adding --gpu-memory-utilization 0.5 and shrinking --max-model-len 32768->8192. Retried at util 0.46. The retry still thrashed the box: unified memory feeds GPU AND OS, so a 2nd ~48GiB model starved the OS -> SSH + UI tracking went down ~13:40-16:20; the kernel OOM-killed the qat-eval-scratch container.

**Observed:** Box recovered with no reboot (24-day uptime held); production :8000 stayed healthy, GPU clean, ~67GiB free afterward. But the run was unsafe: a --gpu-memory-utilization cap alone does NOT make arm C safe on shared unified memory, because the cap governs the GPU fraction while the OS draws from the same pool. The util 0.46 guidance was too aggressive. arm C is abandoned on this box (run-log task exp008_armC_unified_mem_freeze_incident, week1.run.jsonl L1002, status=recovered).

**Would do differently:** On a unified-memory box already hosting a large production model, do not co-locate a second comparably-sized model. Use a smaller arm (arm B, ~15GiB gguf), pause production first, move to a dedicated-GPU box, or SHELVE D-039. Add a serve_qat.sh pre-flight free-memory guard that refuses launch below (arm-need + OS margin) before any retry. Treat a util-fraction cap as necessary-not-sufficient on shared memory.

**Corrections honored:** consumer inviolate rule 4 (validations never silently coerced / error-as-zero), D-040 unattended-Nara autonomy MUST NOT touch inviolate pins/guardrails

## Links

- **derived_from** → `runlog-exp008-armc-unified-mem-freeze-incident-l1002` (run_log_entry)
- **derived_from** → `runlog-exp008-first-live-run-triage-l1001` (run_log_entry)

## Referenced by

- `agent-claude-code-main` (agent) — **authored**
