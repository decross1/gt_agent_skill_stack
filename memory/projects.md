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
**Test command:** no unified runner (no `pytest.ini` / pyproject test config).
`tests/` holds 15 test files (~1,100 LOC); the Day 2–4 suites pass. `plan.yaml`
enumerates per-day validations, run as `.venv/bin/python -m pytest tests/test_*.py`.
`ship` / `health` still assume a single test command — adapting them to a
runner-less, per-day-enumerated suite is on the `plan.md` backlog.
**Notes:**
- Has its own authoritative operating contract — `CLAUDE.md` + `plan.yaml` +
  `run_state/`. That contract wins; this framework's skills only complement it.
- Lead consumer of this agent system. As of 2026-05-21: Week 1, Day 4 complete,
  Day 5 in progress; 49 commits; working tree clean.
- Its **runtime** orchestrator (Gemma 4 / OpenClaw / NemoClaw, sandboxed on the
  Spark) is a separate system from this dev-time framework — see `BOUNDARY.md`.
- Read `PROJECT_CONTEXT.md` → `ARCHITECTURE.md` → `DECISIONS.md` → `plan.yaml`
  to orient before touching it.
