# Harness Integration & Self-Improvement Architecture (`design` Pack)

This document defines how the 5-skill `design` pack (`lab-ui-plan`, `agent-viz`, `lab-ui-build`, `lab-ui-review`, `trace-and-distill`) integrates across the four agent harnesses (**Claude Code**, **Codex**, **Argon / Antigravity**, **Pi**) and the three repositories (`agent_system`, `oracle_system`, `a_bgt_rsi`), and how UI/UX execution closes the loop into the **ReHarness** backward-qualification ledger and **harvest → propose → gate-check** skill-improvement pipeline.

---

## 1. Boundary & Firewall Contract (`BOUNDARY.md` & `verify_pack_boundary.py`)

All five skills in the `design` pack are **Layer B (dev-only)**:

| Skill | Layer | `runtime-safe` | Pack | Primary Role |
|---|---|---|---|---|
| `lab-ui-plan` | B | `false` | `design` | Munzner Nested Model screen brief + Component & State Topology Graph |
| `agent-viz` | B | `false` | `design` | Question-to-representation routing + domain visualization recipes (`design/references/*.md`) |
| `lab-ui-build` | B | `false` | `design` | Token-compliant (`SHARED TOKENS v1`), high-density Tufte craft + honest missingness |
| `lab-ui-review` | B | `false` | `design` | Blocking `design/scripts/qa_gate.py` DOM/HTTP gate + 4-pass visual/domain critique |
| `trace-and-distill` | B | `false` | `design` | Agent Trace 5-tuple logging + MindSkillEvolve distillation into ReHarness & `harvest` |

- **Manifest**: `packs/design.txt` lists the 5 skills in sorted order and is verified by `python3 scripts/verify_pack_boundary.py`.
- **Firewall**: Because `runtime-safe: false`, `./install.sh --target pi` and `./install.sh --verify-firewall pi` automatically exclude all five skills from the autonomous Nara runtime (`~/.pi/agent/skills`), preserving the `BOUNDARY.md` security and self-modification firewall.

---

## 2. Multi-Tool Discovery Wiring (`install.sh`)

`agent_system` (`gt_agent_skill_stack`) is the single source of truth for `.agents/skills/` and `design/`. `install.sh` registers four targets:

| Target | Path | Filter | Agent Profiles |
|---|---|---|---|
| `claude-code` | `~/.claude/skills` | `all` | `~/.claude/agents` |
| `codex` | `~/.codex/skills` | `all` | `(none)` |
| `argon` | `~/.gemini/config/skills` | `all` | `(none)` |
| `pi` | `~/.pi/agent/skills` | `runtime-safe` | `(none)` |

Project-local skill directories also expose the `design` pack directly:
- `agent_system/.agents/skills/<skill>` (and `.claude/skills` symlink bridge)
- `oracle_system/.agents/skills/<skill>` and `oracle_system/.claude/skills/<skill>` (plus `oracle_system/design/`)
- `a_bgt_rsi/.agents/skills/<skill>` and `a_bgt_rsi/run_state/codex_home/skills/<skill>` (and `KNOWN_SKILLS` in `orchestrator/skill_signals.py`)

---

## 3. Closed-Loop Self-Improvement Pipeline

UI/UX skills do not rely on static prose alone. Every UI session feeds three complementary feedback loops:

```
┌──────────────────┐     ┌─────────────────────┐     ┌──────────────────────────┐
│  1. lab-ui-plan  │────▶│  2. lab-ui-build    │────▶│    3. lab-ui-review      │
│   + agent-viz    │     │  (SHARED TOKENS v1) │     │ (design/scripts/qa_gate) │
└──────────────────┘     └─────────────────────┘     └────────────┬─────────────┘
         ▲                                                        │
         │                                                        ▼
┌────────┴─────────┐     ┌─────────────────────┐     ┌──────────────────────────┐
│  5. propose /    │◀────│  4. harvest &       │◀────│  trace-and-distill       │
│  ReHarness qual  │     │  skill_signals.py   │     │ (record_agent_trace.py)  │
└──────────────────┘     └─────────────────────┘     └──────────────────────────┘
```

### Loop A — Deterministic QA Gate → ReHarness Qualification (`reharness-qualification/v1`)
1. `python3 design/scripts/qa_gate.py <html_or_url> --reharness-qual` inspects the static bundle or live URL for:
   - `unknown_badge_ratio <= 0.05` (blocks blanket `"UNKNOWN"` badge dumps; requires explicit `0`, `unmeasured`, `stale`, `failed`, `observed`).
   - `dl_term_count <= 24` (blocks repetitive `<dl>/<dt>/<dd>` key-value dumps where tabular or graphical representations belong).
   - `external_cdn_count == 0` (blocks external font/script leaks on private/Tailscale surfaces).
   - `missing_css_token_count == 0` and `tabular_nums == True` (`SHARED TOKENS v1` compliance).
   - `overflow_px == 0` and semantic `<main>` / `role="tab"` / `aria-live` landmarks.
2. When a check fails or requires human correction, `record_agent_trace.py` (or `qa_gate.py --reharness-qual`) formats a `reharness-qualification/v1` entry with machine-checkable `applies_when` and `falsified_when` predicates (`unknown_badge_ratio > 0.05`, `dl_term_count > 24`, `overflow_px > 0`).
3. In `oracle_system`, `hourglass/reharness_lessons.py` recognizes `"ui_qa_failure"` in `OUTCOME_KINDS` so UI regressions are tracked with the same bitemporal hash-chained rigor as quantitative strategy regressions.

### Loop B — Session Friction → `orchestrator/skill_signals.py` (`a_bgt_rsi`)
- `KNOWN_SKILLS` in `a_bgt_rsi/orchestrator/skill_signals.py` includes `"lab-ui-plan"`, `"lab-ui-build"`, `"lab-ui-review"`, `"agent-viz"`, and `"trace-and-distill"`.
- Whenever a dev-time UI session hits a representation gap or QA gate failure, it emits a `skill_signal` (`gap`, `friction`, `diverged`, or `confirmed`) into `run_state/skill_signals.jsonl`.

### Loop C — `trace-and-distill` → `memory/feedback.jsonl` → `draft_proposals.py` (`agent_system`)
- At the end of a UI session, `trace-and-distill` logs the Agent Trace 5-tuple (`what`, `when`, `who`, `why`, `where`) via `design/scripts/record_agent_trace.py` and appends structured findings to `memory/feedback.jsonl`.
- Running `python3 scripts/draft_proposals.py` aggregates `memory/feedback.jsonl` by skill and drafts bounded diffs against `.agents/skills/<skill>/SKILL.md` or `design/references/<domain>.md` for human ratification via `propose` and `gate-check`.
