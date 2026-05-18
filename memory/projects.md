# Project Registry

A cross-project index for this machine. The roadmap goal is machine-wide project
awareness; today this file is maintained manually. Add a row per project the
agent system should know about.

Format:

```
## <project-name>
**Path:** <absolute path>
**Kind:** <research pipeline | library | app | ...>
**Stack:** <language / key frameworks>
**Test command:** <...>
**Notes:** <anything an agent should know before touching it>
```

---

## a_bgt_rsi
**Path:** `/home/decross1/projects/a_bgt_rsi`
**Kind:** research apparatus — contract-governed, plan-driven ML/research pipeline
**Stack:** Python 3.12 (apparatus core); some TypeScript / TSX (UI surface).
Runtime: vLLM-served Gemma 4 26B MoE + ChromaDB/BGE-M3 on an NVIDIA DGX Spark.
**Test command:** _not yet established_ — no unified runner (no `pytest.ini` /
pyproject test config); `tests/` is empty. `plan.yaml` references per-day
validation scripts (`python3 tests/test_*.py`) that don't exist yet. Revisit
the `ship` / `health` skills' assumptions once the test apparatus is built.
**Notes:**
- Has its own authoritative operating contract — `CLAUDE.md` + `plan.yaml` +
  `run_state/`. That contract wins; this framework's skills only complement it.
- Primary consumer of this agent system. Currently Week 1, Day 1 in progress.
- Its **runtime** orchestrator (Gemma 4 / OpenClaw / NemoClaw, sandboxed on the
  Spark) is a separate system from this dev-time framework — see `BOUNDARY.md`.
- Read `PROJECT_CONTEXT.md` → `ARCHITECTURE.md` → `DECISIONS.md` → `plan.yaml`
  to orient before touching it.
