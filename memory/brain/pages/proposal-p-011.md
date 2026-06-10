---
slug: "proposal-p-011"
type: "proposal"
date: "2026-06-10"
source: "memory/brain/proposals.jsonl"
---

# P-011 — Env-gated stubs must be asserted per-shell, not assumed from the interactive default

_agent: claude-code-main_

**Verdict:** `open`

**Target:** rule → `mock-llm-discipline`

**Change:** Where a project gates real-model behavior on an env var set in the human's interactive shell (a_bgt_rsi: MOCK_LLM=1), every NON-interactive invocation (pytest, agent shells, cron) must set it EXPLICITLY (e.g. `MOCK_LLM=1 pytest ...`), and session startup should verify with `env | grep` rather than trusting a memory note. Consider adding the assertion to the resume-state/gate-check preflight.

**Reasoning:** 2026-06-10 (a_bgt_rsi): MOCK_LLM=1 lives in the interactive shell only; Claude Code's non-interactive bash had it UNSET, so the test suite silently made REAL Gemma calls via orchestrator/topicality.py during pytest runs and stamped them with a stale fixture run_id (rows landed in the canonical logs/calls.jsonl). The standing memory note ('MOCK_LLM=1 is set in the user's shell by default') was true for the interactive shell and false for every shell that matters to automation. Found while building the D-048 no-live-artifacts guard; the zero-delta check exposed +5 rows.
