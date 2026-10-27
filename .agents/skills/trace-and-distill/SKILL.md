---
name: trace-and-distill
description: Record Agent Trace 5-tuples (what, when, who, why, where) for UI/UX changes and distill qa_gate.py / review findings into ReHarness backward qualifications, skill_signals, and harvest feedback entries. Use at the end of a UI build or review session.
layer: B
runtime-safe: false
pack: design
---

# `trace-and-distill` — Agent Trace Logging & MindSkillEvolve Distillation

## When to Use
Invoke `trace-and-distill` after `[[lab-ui-review]]` to record provenance for UI mutations and convert any friction, representation defect, or QA gate violation into durable skill/reference improvements across `agent_system`, `oracle_system`, and `a_bgt_rsi`.

## Step 1 — Record the Agent Trace 5-Tuple (`record_agent_trace.py`)

Every non-trivial UI overhaul records a deterministic `agent-trace/v1` entry with `what`, `when`, `who`, `why`, and `where`:
```bash
python3 design/scripts/record_agent_trace.py \
  --what "oracle_harness/portal_view/{index.html,styles.css,app.js}" \
  --who "codex/argon-design-pack" \
  --why "Replace <dl> UNKNOWN dumps with SHARED TOKENS v1 KPI strips, quota bullet bars, Tufte tables, and pan/zoom/ego-highlighted SVG Atlas" \
  --where "$(git rev-parse --short HEAD)" \
  --skills "lab-ui-plan,agent-viz,lab-ui-build,lab-ui-review,trace-and-distill"
```

## Step 2 — Distill Failure Modes into ReHarness Qualifications

When `design/scripts/qa_gate.py --reharness-qual` surfaces a violation (or when human review corrects a representation choice), emit a backward qualification row (`reharness-qualification/v1`) via `record_agent_trace.build_qualification_row`:
- **`applies_when`**: surface and task predicates (e.g., `surface_kind in ["portal_8790", "cockpit_8765", "lab_5173", "brain_5180"]`).
- **`falsified_when`**: machine-checkable metric predicates (`unknown_badge_ratio > 0.05`, `dl_term_count > 24`, `overflow_px > 0`, `external_cdn_count > 0`).
- **`scope_narrowing`**: concrete constraint added to the skill or reference doc so future sessions cannot repeat the failure.
- In `oracle_system`, `hourglass/reharness_lessons.py` supports `"ui_qa_failure"` in `OUTCOME_KINDS` for bitemporal lesson tracking.

## Step 3 — Feed `harvest`, `skill_signals.py`, and `propose`

1. **In `agent_system`**: append a `memory/feedback.jsonl` entry (`confirmed`, `diverged`, `gap`, or `friction`) naming the exercised design skill (`lab-ui-plan`, `agent-viz`, `lab-ui-build`, `lab-ui-review`, or `trace-and-distill`) and run `python3 scripts/draft_proposals.py` when ready to propose a skill or `design/references/*.md` diff.
2. **In `a_bgt_rsi`**: call `orchestrator.skill_signals.emit_skill_signal(skill=..., signal_class=..., evidence=...)` so dev-time UI skill friction is captured in `run_state/skill_signals.jsonl`.
