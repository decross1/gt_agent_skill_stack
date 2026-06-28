# Agent System — Improvement Plan

This plan governs the framework's own development. The framework is **executed as
a plan-driven project using its own skills** — `resume-state` → `harvest` →
`gate-check` → execute → `validate` → `run-log`. Improving the framework is
therefore also the framework's largest continuous test of its own Layer-A
discipline.

- **This plan** — `plan.md` — is authoritative. It is **re-sorted every session**
  from the feedback ledger.
- **State file** — `run_state/framework.state.json` — authoritative on resume.
- **Run log** — `run_state/framework.run.jsonl` — append-only, one entry per task.
- **Feedback ledger** — `memory/feedback.jsonl` — append-only, harvested from the
  lead consumer `a_bgt_rsi`.

Created 2026-05-21. Plan version 1.

---

## Charter — the framework's falsifiable claim

The framework demanded a hypothesis, a baseline, a metric, and a decision rule of
every project it touches, while having none for itself. That stops here.

**Mission.** A portable framework that makes agentic development — and
autonomously spawned agents — more disciplined, auditable, and reliable, in *any*
system. `a_bgt_rsi` is the lead consumer that informs it; it is not the only
intended consumer.

**Two claims, two tests — they are different and need different consumers:**

| Claim | What it asserts | Tested by |
|---|---|---|
| **Fidelity** | Each Layer-A skill is an accurate, complete, low-friction description of disciplined practice. | `a_bgt_rsi` — already maximally disciplined, so it can confirm *accuracy*, not *uplift*. |
| **Uplift** | A consumer that adopts the runtime-safe core produces a complete audit trail it would not produce without the framework. | A second, *less* disciplined consumer (Phase 4). `a_bgt_rsi` structurally cannot test this. |

**Metrics.**
- **Conformance** — per skill, `Confirmed` vs `(Diverged + Friction)` findings over
  the last 2 harvests.
- **Open gaps** — count of `gap` findings not yet turned into a skill or section.
- **Audit completeness** (uplift) — on the second consumer, share of fallbacks
  logged / gates honored / validations not coerced, measured with vs. without the
  framework.

**Decision rules** (written before the work, per `plan-research`):
- A skill is **hardened** when 2 consecutive harvests yield no new `Diverged` or
  `Friction` finding against it.
- **v1.0 ships** when: every Layer-A skill is hardened **and** open gaps = 0
  **and** portability is verified on Pi **and** the uplift test passes on a
  second consumer.

---

## How a session runs (the dogfood loop)

1. **`resume-state`** — read this plan + `framework.state.json`; find the resume
   session and the first incomplete task.
2. **`harvest`** — read `a_bgt_rsi`'s activity since the stored watermark; append
   findings to `memory/feedback.jsonl`; advance the watermark. *(From Session 2.)*
3. **Re-sort the backlog** — re-prioritize from `feedback.jsonl`. New `friction`/
   `gap` findings can pre-empt the planned session order.
4. **`gate-check`** — before any gated or irreversible task.
5. **Execute** the session's tasks.
6. **`validate`** — each task's pass-signal as an independent check; never coerce.
7. **`run-log`** — append one entry per task to `framework.run.jsonl`.
8. **`context-save`** — refresh `memory/session-latest.md`; durable decisions to
   `memory/DECISIONS.md`.

---

## The feedback loop (`a_bgt_rsi` → framework)

`a_bgt_rsi` already emits a complete behavioral trace — `run_state/week1.run.jsonl`,
`DECISIONS.md` (D-001…), git history. The framework **reads it; it does not modify
`a_bgt_rsi`** (that project is contract-governed; changing it needs its own gates).

Each harvest reads everything new since the watermark and classifies it **per
skill**:

| Class | Meaning | Becomes |
|---|---|---|
| `Confirmed` | `a_bgt_rsi`'s behavior matched the skill's prescription. | Evidence the skill is accurate — keep. |
| `Diverged` | `a_bgt_rsi` did it differently or contrary to the skill. | Investigate: the skill is wrong, or the project is. |
| `Gap` | `a_bgt_rsi` needed discipline no skill covers. | New-skill / new-section candidate. |
| `Friction` | Invoking the skill *as written* would have been awkward or redundant. | Skill edit candidate. |

**Watermark** lives in `framework.state.json`:
`{ "a_bgt_rsi": { "run_jsonl_lines": N, "last_commit": "<sha>", "last_decision": "D-0NN" } }`.

**Feedback entry shape** (`memory/feedback.jsonl`, append-only):
```json
{"harvest_id":"H001","date":"<ISO>","source":"a_bgt_rsi","skill":"validate",
 "class":"confirmed","evidence":"run.jsonl task_id=day4_end_of_day_artifacts: status=partial_pass with finding field, threshold not coerced",
 "plan_candidate":null}
```

Every `Diverged`/`Gap`/`Friction` finding becomes a backlog item. The backlog is
the input to step 3 of every session.

---

## Target structure — three layers

The 16 skills are one flat list today; they have three different levels of
generality. The plan separates them (Phase 2) without breaking symlinks — via
`layer` and `runtime-safe` frontmatter, not directory renames.

| Layer | Skills | Role |
|---|---|---|
| **A — Core discipline** | `resume-state`, `gate-check`, `validate`, `run-log`, `fallback`, `spawn-contract` | Domain-agnostic. The product. |
| **B — Research vertical** | `plan-research`, `experiment`, `auto-experiment`, `repro-check`, `investigate`, `code-review`, `ship`, `health` | One optional vertical pack among future ones. |
| **C — Orchestration & meta** | `orchestrate`, `harvest`, agent profiles, `context-save/restore` | Infrastructure. |

**Runtime-safe core** = the subset of Layer A that may be embedded in a spawned
or runtime agent: `gate-check`, `validate`, `run-log`, `fallback`, `resume-state`, `spawn-contract`
— rewritten (Phase 5) to assume no human in the loop and no dev harness.

---

## Sessions

Phases 0–2 (Sessions 1–6) are **fixed** — they stand up the loop and resolve the
framework's identity. Sessions 7+ are **feedback-driven**: order and count flex
with the harvest. A minimum-viable arc completes at Session 6; the full arc at
24 (extended from 20 on 2026-05-24 to add Phase 3.5 — The Brain, S13–S16).

### Phase 0 — Stabilize & bootstrap

**Session 1 — Stop the bleeding; scaffold the dogfood harness.** ✅ *Done 2026-05-21.*
- 1.1 Resolve the boundary leak. `install.sh --global` symlinked all 16 skills
  into `~/.pi/agent/skills/`; `a_bgt_rsi`'s Day-6 Pi runtime would inherit them.
  Remove the Pi-global symlinks and make `install.sh` Pi-global opt-in. *(Gate:
  changes install behavior — human nod. Reversible.)*
- 1.2 Fix concrete doc errors: refresh `memory/projects.md` to `a_bgt_rsi`'s real
  state (Day 4 done / Day 5 in progress, `tests/` populated); correct "13 skills"
  → "16" in `BOUNDARY.md` and `AGENTS.md`; append a `DECISIONS.md` entry
  correcting the "autoresearch" misnomer (the consumer is `a_bgt_rsi`).
- 1.3 Scaffold the harness: create `run_state/framework.state.json`,
  `run_state/framework.run.jsonl`, `memory/feedback.jsonl`.
- 1.4 Append a `DECISIONS.md` entry ratifying this plan: agnostic re-scope,
  dogfooded execution, runtime-safe core.
- **Pass-signal:** `BOUNDARY.md` verification shows no Pi-global leak; `grep "13"`
  finds no stale count; state file, run log, and feedback ledger exist and parse.

### Phase 1 — Build the feedback loop

**Session 2 — Build the `harvest` skill.** ✅ *Done 2026-05-21.*
- 2.1 Author `.agents/skills/harvest/SKILL.md`: read a consumer's run log + git +
  decisions since a watermark, classify per skill, append to `feedback.jsonl`,
  advance the watermark. Written generally (any consumer), with `a_bgt_rsi` as the
  worked example.
- 2.2 Dry-run `harvest` over a small slice of `a_bgt_rsi` history.
- **Pass-signal:** `harvest` produces well-formed `feedback.jsonl` entries; the
  watermark advances; a re-run from the new watermark is idempotent (no dupes).

**Session 3 — First full harvest; baseline conformance report.** ✅ *Done 2026-05-21.*
- 3.1 Run `harvest` over all `a_bgt_rsi` history (preflight → current day).
- 3.2 Produce the baseline conformance report: per skill, `Confirmed` /
  `Diverged` / `Gap` / `Friction` counts.
- 3.3 Seed the backlog (below) from the findings.
- **Pass-signal:** every skill has a baseline classification; the report
  distinguishes fidelity-confirmed skills from those with open findings.

### Phase 2 — Resolve identity & structure

**Session 4 — Re-layer the skills.** ✅ *Done 2026-05-21.*
- 4.1 Add `layer: A|B|C` and `runtime-safe: true|false` frontmatter to every
  `SKILL.md`. No directory renames (symlinks must survive).
- 4.2 Rewrite `AGENTS.md` to present the three layers and the runtime-safe core.
- **Pass-signal:** every skill carries both fields; `AGENTS.md` layer tables match
  the frontmatter exactly.

**Session 5 — Rewrite `BOUNDARY.md` as a layering rule.** ✅ *Done 2026-05-21.*
- 5.1 Replace the blanket "dev-time only" ban with: dev-only skills (Layers B/C)
  vs. runtime-safe core (the 5 Layer-A skills). Define what `runtime-safe`
  *requires* of a skill — no assumed human, no PR/harness calls, minimal context
  cost.
- 5.2 Append a `DECISIONS.md` entry; this supersedes the 2026-05-18 scope-boundary
  decision. *(Gate: reverses a standing rule — explicit ratification required.)*
- **Pass-signal:** `BOUNDARY.md` defines both classes and the `runtime-safe`
  contract; the leak-verification section still holds for Layers B/C.

**Session 6 — Decouple `a_bgt_rsi`-isms from the core.** ✅ *Done 2026-05-21.*
- 6.1 Move project-specific names (Gemma 4 / OpenClaw / NemoClaw / DGX Spark /
  "Day 6") out of `AGENTS.md` and `BOUNDARY.md` into `memory/projects.md`.
- 6.2 Make core-doc examples project-neutral.
- **Pass-signal:** `grep` of core docs for `a_bgt_rsi`-specific terms returns only
  `projects.md` and the `harvest` worked example.

### Phase 3 — Skill hardening, feedback-driven (Sessions 7–12, elastic)

Each session: `harvest` the latest `a_bgt_rsi` activity → pick the highest-priority
open finding from `feedback.jsonl` → improve that skill → re-validate. **The
specific skill per session is chosen at session start, not pre-assigned here.**
Known candidates already on the backlog: `orchestrate` (worktree / file-boundary
protocol), `ship` (no-unified-runner assumption), `health` (stale test
assumption), and runtime-safe rewrites of the Layer-A core.

- **Pass-signal (per session):** the chosen skill's `Diverged`/`Friction` findings
  are resolved — skill edited, or the finding marked a deliberate non-change with
  a reason — and a re-harvest shows no regression.
- **Sessions done:** S7 ✅ — `orchestrate` parallel-worktree protocol (2026-05-22).
  S8 ✅ — `decision-log` skill created (2026-05-22).
  S9 ✅ — `validate` mis-specified-criterion protocol + `partial_pass` (2026-05-22).
  S10 ✅ — `run-log` status enum expanded and defined (2026-05-23).
  S11 ✅ — `ship` integration flow + no-unified-runner; `health` light touch (2026-05-23).
  S12 ✅ — `gate-check` attestation- vs verification-cleared gates (2026-05-23).

### Phase 3.5 — The Brain (Sessions 13–16)

A research-tuned observation + reflection + proposal-review engine. Inspired
by gbrain (Garry Tan) but file-first, write-only on the apparatus runtime, and
strictly dev-time (no new Layer-A skill, explicit firewall against
inheritance into apparatus-runtime skill discovery). Full durable plan at
`~/.claude/plans/mighty-munching-fairy.md`; this section is the sequencing
view. Falsifiable claim: reduces files-opened to reconstruct a day's
apparatus activity from 6+ to ≤ 1; bounded `brain-recall` reduces agent
drift across sessions. Each phase carries a kill-switch metric.

**Session 13 — Phase B0: minimal substrate.**
- 13.1 Insert Phase 3.5 into `plan.md`; renumber Phase 4 → S17–S20 and
  Phase 5 → S21–S24.
- 13.2 Create `memory/brain/narratives.jsonl` (empty, append-only) +
  `memory/brain/view/.gitkeep`.
- 13.3 Author `.agents/skills/narrate/SKILL.md` (Layer B, runtime-safe
  false) — end-of-task reflection writeback.
- 13.4 Author `scripts/render_brain.py` — joins `week1.run.jsonl` +
  `framework.run.jsonl` + `narratives.jsonl` + `DECISIONS.md` →
  `memory/brain/view/<YYYY-MM-DD>.md`.
- 13.5 Author `scripts/ingest_apparatus.py` — deterministic projection of
  `a_bgt_rsi/logs/*.jsonl` into `narratives.jsonl` as `apparatus_event`
  entries. Idempotent.
- 13.6 Edit `resume-state` to surface last N `correction:`-flagged
  DECISIONS.md entries in the briefing.
- 13.7 Edit `context-restore` to surface the same.
- 13.8 Edit `decision-log` to document the `correction:` flag convention.
- **Deferred harvest note.** A_bgt_rsi has advanced 26 commits and 38
  run-log lines (`5fe49b9`, week1.run.jsonl line 134) since the H004
  watermark — Day 7 PD experiment, Week-1 retrospective attestation, Day
  8 cleanup. Per the living-plan rule, the harvest is **deferred**, not
  papered over — it is logged as the next session's first task (S14).
  Rationale: the brain build is the higher-priority short-term upside the
  user named, and `ingest_apparatus.py` will surface the new apparatus
  activity into the rendered view as a side effect of B0 validation.
- **Pass-signal:** `render_brain.py --day 2026-05-23` collapses ≥ 4 source
  files (week1.run.jsonl, framework.run.jsonl, DECISIONS.md, narratives.jsonl)
  into one view; `narrate` writes well-formed JSONL; ingest is idempotent.
- **Kill switch:** if the rendered view isn't usable, halt before S14.

**Session 14 — Phase B1: typed edges + page projection + graph visual.**
- First: run the deferred S13 harvest (a_bgt_rsi 224d284..5fe49b9, run.jsonl
  lines 97–134, DECISIONS up to D-027 → current).
- Then: create `memory/brain/edges.jsonl` (append-only). Extend `narrate`
  to declare typed edges at write-time. Author `scripts/project_pages.py`
  (page projection). Author `memory/brain/view/graph.html` (vendored
  visualizer). Edit `experiment` and `harvest` to emit edges.
- **Pass-signal:** graph visualizes the Day 4 anomaly with its lineage
  `hypothesis → experiment → anomaly → correction`; backlinks consistent;
  no orphan edges.
- **Kill switch:** if the graph adds no insight beyond the per-day view,
  halt before S15.

**Session 15 — Phase B2: proposal-review loop + rules.md.**
- Create `memory/brain/proposals.jsonl` + `memory/brain/rules.md`
  (regenerated). New skills `propose`, `review-proposal`. Author
  `scripts/regen_rules.py` digesting `correction:`-flagged DECISIONS.md.
  Encode auto-reject logic against active rules.
- **Pass-signal:** ≥ 3 proposals through the loop (≥ 1 each accept /
  reject / human-review); accepted proposals materialize as new
  DECISIONS.md entries with `supersedes:` chains where applicable.
- **Kill switch:** if no proposals filed in 2 sessions, remove the loop.

**Session 16 — Phase B3: `brain-recall` with bounded read + firewall.**
- New skill `.agents/skills/brain-recall/SKILL.md` (Layer B, dev-time).
  Bounded query: top-N by `(recency × tag-match × scope)`. Active-correction
  filter (not-superseded + `last_reviewed` window).
- `install.sh` excludes brain skills from `--global-pi`. `BOUNDARY.md` gets
  a new firewall section with a verification command.
- **Pass-signal:** `brain-recall` returns ≤ K tokens per query; apparatus
  runtime skill list contains no brain skill; firewall verification passes.
- **Kill switch:** if no dev-time agent voluntarily invokes `brain-recall`
  over 2 sessions, drop it.

### Phase 4 — Portability & uplift

**Session 17 — Pi migration check** (the long-deferred Task 5). Verify the
framework loads and runs in Pi; verify the runtime-safe core can be loaded into a
Pi runtime agent without the dev-only layers.

**Session 18 — Install/discovery abstraction.** Generalize `install.sh` beyond
hardcoded `~/.claude` and `~/.pi` toward a discovery story for "any system."

**Sessions 19–20 — Onboard a second, weaker consumer** *(Gate: human picks the
consumer — toy or real)*. Run it with and without the runtime-safe core; measure
audit completeness. This is the **uplift test** `a_bgt_rsi` cannot provide.

### Phase 5 — Autonomy & generalization

**Sessions 21–22 — Make "autonomously spawned agents" first-class.** A spawned
agent receives a task contract, the runtime-safe core, a self-gating protocol, a
self-reporting protocol, and an explicit authority boundary. Likely a new
`spawn-contract` template skill.

**Session 23 — Package Layer B as an optional vertical pack** and document how to
add other verticals (product, data-pipeline, …).

**Session 24 — v1.0.** Rewrite `README.md`/`AGENTS.md` for "any system"; final
harvest; retrospective; check the Charter's decision rule against accumulated
evidence.

### Phase 6 — Dynamic governance surface

**Session 25 — Dynamic proposal-review brain.** Make the proposal-review loop
interactive and frictionless. The static brain view + terminal verdict CLI
(S15/S16) become a localhost, LLM-assisted *amend-then-decide* surface.
- First: stand up `scripts/brain_server.py` (stdlib `ThreadingHTTPServer`,
  127.0.0.1:5180) serving the file-first brain view AND the JSON API
  (`/api/proposals`, `/api/proposal/<P-NNN>`, `…/discuss`, `…/verdict`,
  `…/handoff`); only FRAMEWORK-scoped proposals are surfaced
  (`proposal_scope()` in `scripts/project_summary.py`).
- Then: wire discuss/amend to the local LLM (Gemma 4 @ 127.0.0.1:8000), persist
  every card + discussion turn append-only to
  `memory/brain/proposal_cards.jsonl`, and route Accept/Reject/Request-revision
  through the blessed `scripts/review_proposal_cli.py` via argv (D-046 pattern,
  `human:ui` stamp). Add one-click dev-agent handoff export. Governance recorded
  in DECISIONS.md (2026-06-15) and BOUNDARY.md (firewall: dev-time, 127.0.0.1).
- **Pass-signal (smallest falsifiable experiment):** on one real open proposal,
  a discuss→amend loop yields a *measurably cleaner* proposal than the raw draft
  — operationalized as the amended card resolving ≥ 1 `rule_check.conflict` /
  ambiguity the raw draft left open (or a human-judged "now decidable" where the
  raw draft was not) — AND the verdict is **one click**: a single Accept appends
  exactly one `human:ui`-stamped outcome to `proposals.jsonl` via the blessed CLI
  with no terminal step, and Export-handoff returns a written path. Determinism
  check: re-running projection/regen reproduces the brain view byte-for-byte
  without any LLM call.
- **Kill switch:** if the discuss→amend loop does not make a proposal more
  decidable than the static view did (no conflict resolved, no human-judged
  uplift) over 2 reviews, retire `brain_server.py` and revert to the static view
  + terminal `review_proposal_cli.py`; `proposal_cards.jsonl` is discardable
  draft cache (governed verdicts live in `proposals.jsonl`).

### Phase 7 — Self-auditing & self-healing discipline

**Direction (2026-06-28).** The framework's working north star is reframed: from
proving *uplift* on a second, less-disciplined consumer (Sessions 19–20, still
**deferred** — not abandoned) to **a framework that audits and heals its own
discipline.** Success is now measured by whether the harvest → drift → draft →
review → enacted loop actually closes on the framework's *own* skills. The
Charter's fidelity/uplift claims remain on record; this is a reprioritization,
logged in `DECISIONS.md` (2026-06-28).

**Session 26 — Light up the self-healing loop.** The loop was *built* out-of-band
(committed Jun 16–18, reconciled into this plan 2026-06-28): deterministic drift
detection (`scan_drift.py` → `drift_signals.jsonl`), runtime self-reporting
(apparatus `skill_signals.jsonl` ingested read-only into `drift_signals`, source
= `runtime`; coordinated with `a_bgt_rsi` D-056), bubbling of drift + harvest
findings into **draft** proposals (`draft_proposals.py`), graduated routing by
blast radius (`blast_radius.py` low|high; `graduate_drafts.py` with the
`adversarial_gate` stubbed closed), a first-class **draft** lifecycle lane, and an
honest-loop dashboard (harvest → candidates → proposals → review → enacted). 76
tests pass; `BRAIN_AUTODRIFT` gates the live wiring (default off).

The loop is **built and tested but UNPRIMED** — `drift_signals.jsonl` empty, no
draft proposals, apparatus not yet emitting `skill_signals.jsonl`. Priming
(2026-06-28) exposed two misfires that must be fixed *before* the loop emits its
first real signal:
1. **`scan_drift` verdict false-positive.** `runlog_failure` flags any framework
   skill whose run-log `status` is failure-ish. But a *verdict-rendering* skill
   (`validate`, `repro-check`, `gate-check`, `code-review`) honestly returning
   `failed` is the skill **working**, not drifting — its job is "never coerce a
   near-miss into a pass." Both candidate signals (validate `failed` on
   `lit_battery_post_t1_final` L1135 and `d050-decision-run` L1432) are exactly
   this: a legitimate FAIL verdict on a thing that genuinely failed. The detector
   must distinguish "the skill could not complete" (aborted/escalated/halted =
   drift, all skills) from "the skill rendered a negative verdict"
   (failed/partial_pass = not drift for verdict skills).
2. **`draft_proposals` resolved-finding gap.** Bubbling the H001–H008 backlog
   would file drafts for fixes already shipped (a "new skill `decision-log`"
   draft when `decision-log` exists; `slip-ladder`; the resume-state gate-hold
   finding already enacted as FR-002). The bubbler must skip a finding whose
   remedy already exists (skill present / active rule covering it).

- **Pass-signal (smallest falsifiable experiment):** after the two fixes, a live
  `scan_drift --apply` over the run logs produces **only** signals that name a
  genuine skill malfunction (a skill that could not complete, or a non-verdict
  skill that failed) — zero verdict false-positives; each such signal bubbles to
  exactly one **draft** candidate that appears in the dashboard's *candidates*
  lane and the *needs-you* inbox as `candidate_review`, and **nothing
  auto-enacts** (no SKILL.md / rule / DECISIONS edit). The auto path stops at a
  recorded verdict + handoff for low-blast-radius drafts only, and the
  `adversarial_gate` stays closed until deliberately, separately opened.
- **Kill-switch:** if priming produces signal that is mostly false-positive or
  stale even after the two fixes, leave `BRAIN_AUTODRIFT` off and keep the loop in
  dry-run/observation mode — detection and bubbling remain manual, human-reviewed
  scripts, and the honest-loop dashboard reports an empty-but-truthful candidates
  lane rather than a noisy one.

**Audit (2026-06-28).** Lit via Option 3, primed, then independently audited — the
audit found, and this fixed, two things: (1) a supersession over-suppression bug
that dropped two still-open findings (fallback H002, repro-check H003) on a false
"confirmed clean" basis — a harvest now counts as *clean* for a skill only if it
confirms it AND carries no open finding on it; and (2) an over-claim — the **drift**
lane is trustworthy from day one (Option 3, emits 0), but the harvest-**backlog**
candidates are a human-triage list, not a guaranteed-all-open set. The bubbler's
resolved-finding guards are *proposes-an-existing-skill* + *clean-harvest
supersession*; rule-coverage and session-hardening are deliberately not automated
(too fragile — they risk dropping real findings), so a few already-addressed
findings (ship, resume-state) bubble for a human to discard. See DECISIONS 2026-06-28
(FR-008 drift-semantics, FR-009 audit corrections).

---

## Backlog (re-sorted every session from `feedback.jsonl`)

### Re-sort — Session 24 (2026-06-14), from harvest H008

Harvest **H008** (`a_bgt_rsi` D-030..D-052, run-log L155–1541) appended 22
findings: 12 confirmed, 1 diverged, 6 friction, 3 gap. Re-sorted below; older
re-sorts kept as history beneath.

**Hardening dashboard** (rule: 2 *consecutive* clean harvests with active
confirmation and no open gap):

| Skill | Status | Evidence |
|---|---|---|
| `gate-check` | ✅ **hardened** | confirmed H002→H008 (5 clean rounds, last D/F was H001) |
| `validate` | ✅ **hardened** | confirmed H003,H007,H008 (3 clean rounds) |
| `decision-log` | ✅ **hardened** | confirmed H005,H007,H008 since the founding H002 gap |
| `code-review` | ✅ **hardened** | confirmed H002 + H008, never any D/F |
| `investigate` | ✅ **hardened** | confirmed H002 + H008, never any D/F |
| `plan-research` | ◻ provisional | first confirmation H008 — needs one more clean harvest |
| `slip-ladder` | ◻ provisional | first confirmation H008 — needs one more clean harvest |
| `resume-state` | ◻ quiet | last touch H006/friction; silent since — needs active re-confirmation |
| `ship` | ◻ quiet | last touch H002/friction; silent since — needs active re-confirmation |
| `run-log` | ❌ open | 3 new friction in H008 (status synonyms / `deferred` / session-marker pollution) |
| `spawn-contract` | ❌ open | H008 diverged (D-032) + gap (no contract artifact at spawn) |
| `experiment` | ❌ open | H008 friction (no-ledger, recurs) + gap (incident/recovery) |
| `fallback` | ❌ open | H008 friction (blocked-primary→fallback dual-logged) |
| `repro-check` | ❌ open | H008 gap (single REAL run flips a gate; repro-check never invoked) |
| `orchestrate` | ❌ open | H008 friction — but D-042 dispositions it referenced-only by design |

**P1 — gaps (new from H008, in priority order)**
- `repro-check` is never invoked at the point it governs: results-changing gate
  on/off decisions ride on a *single* REAL battery run. Require a repro-check (or
  a logged variance waiver) before one run flips a pre-registered gate.
  *(H008 repro-check/gap)*
- `spawn-contract` is enforced in limb prose ("spawn-contract honored") but emits
  no machine-checkable contract record at spawn. Emit the contract artifact at
  spawn time. *(H008 spawn-contract/gap; relates to filed P-004, P-018)*
- No incident/recovery discipline: an OOM hang logged ad-hoc `recovered`, a
  preflight resource gate added reactively. Give `experiment` (or a new section)
  a preflight resource gate + post-incident record. *(H008 experiment/gap)*

**P2 — friction (new from H008)**
- `run-log` status synonym drift: `success`/`completed`→`passed`,
  `error`/`timeout`→`failed`. Document enum aliases or normalize on ingest.
  *(H008 run-log/friction)*
- `run-log` has no enum home for `deferred`/carryover work (postponed past its
  window, distinct from skipped/aborted). Add a first-class status.
  *(H008 run-log/friction)*
- `run-log`: session-lifecycle markers (`open`/`closed`/`applied`/
  `ready_to_remove`, empty observable fields) pollute the executed-step stream.
  Separate stream or a `kind` field. *(H008 run-log/friction)*
- `fallback`: a single blocked-primary→fallback transition logs as two divergent
  outcomes (`partial` + `passed`). Define a single-entry representation
  (status + carryover field). *(H008 fallback/friction; extends the H002
  gated-fallback-selection item)*
- `experiment` mandates a separate `experiments.md`; the consumer uses the run
  log + DECISIONS.md. Allow the run log to be the ledger. *(H008 + H002,
  recurring — still open)*
- `orchestrate` referenced-only: D-042 routes decomposition to the harness-native
  Workflow primitive. **Disposition:** mark `orchestrate` (and `plan-research`,
  per D-042) *hardened-as-referenced* so harvest stops re-opening settled
  friction; optionally teach `orchestrate` to defer to a native workflow
  primitive when present. *(H008 orchestrate/friction)*

**P3 — structural / policy (from H008 diverged)**
- **BOUNDARY firewall vs research-orchestrator consumers.** D-032: `a_bgt_rsi`
  deliberately installed *all 24 skills* (incl. dev-only) with no runtime-safe
  filter, contradicting the firewall, on the grounds it is a research
  orchestrator not a customer runtime. Needs a policy decision: a per-project
  exception, a third class between dev-only and runtime-safe, or an enforced
  re-pin. *(H008 spawn-contract/diverged)*

### Re-sort — Session 3 (history)

Re-sorted **Session 3** from harvests H001–H002 — 25 findings, see
`memory/conformance.md`. Priority: gaps, then friction, then structural. Each
item cites the harvest finding(s) behind it.

**P1 — gaps (a skill is missing or silent)**
- ✅ **addressed S7** — `orchestrate` gained a parallel-worktree execution
  protocol (file-boundary allow-lists, mock isolation, pre-merge boundary
  verification, `--no-ff` merges, completion sentinels). Re-harvest pending to
  confirm and mark hardened. *(H002 orchestrate/gap)*
- ✅ **addressed S8** — created the `decision-log` skill (mandatory
  Alternatives + Reversibility + supersedes-chains); the framework's
  `DECISIONS.md` template updated to match. *(H002 decision-log/gap)*
- No skill for autonomously spawned agents — task contract, self-gating,
  self-reporting, authority boundary. *(Phase 5; 2026-05-21 analysis)*

**P2 — friction (a skill exists but mis-fits real use)**
- ✅ **addressed S9** — `validate` gained a "When the criterion itself is
  wrong" protocol (verify intent separately, report the criterion as
  mis-specified, escalate, never coerce). *(H002 validate/friction)*
- ✅ **addressed S9 (validate) + S10 (run-log)** — `validate` gained a
  tightly-scoped `partial_pass` overall verdict; `run-log`'s status enum
  gained `partial_pass` (with `started` and `escalated`). *(H002 validate/friction)*
- ✅ **addressed S10** — `run-log`'s status enum expanded to `started` /
  `passed` / `partial_pass` / `failed` / `aborted` / `halted` / `escalated` /
  `skipped`, each defined; enum declared a default a project may extend.
  *(H001 + H002 + H003)*
- ✅ **addressed S11** — `ship` step 5 generalized into "Integrate" with three
  named flows (PR-based, commit-to-main, worktree-merge); Rules use
  "integration message" not "PR". *(H002 ship/friction)*
- ✅ **addressed S11** — `ship` step 2 + `health` step 1 handle projects with
  no unified runner — an enumerated per-unit test set is "the suite".
  *(H002 ship/friction)*
- ✅ **addressed S12** — `gate-check` now defines two clearance modes
  (attestation-cleared, verification-cleared) and refines the "never silently
  clear" rule. *(H001 gate-check/friction)*
- `fallback` does not address a fallback *selection* that is itself gated.
  *(H002 fallback/friction)*
- `experiment` mandates a separate `experiments.md`; allow the run log to be
  the ledger. *(H002 experiment/friction)*
- `repro-check` has no check that a run was not silently mocked/stubbed — a
  stray `MOCK_LLM` flag faked a result in `a_bgt_rsi`. *(H003 repro-check/friction)*

**P3 — structural**
- `memory/` does three jobs (framework-self memory, cross-project registry,
  consumer templates) with no separation. *(2026-05-21 analysis)*

**Untested by `a_bgt_rsi`** — need a different consumer (Phase 4 uplift test):
`plan-research`, `health`, `auto-experiment`, `context-save`, `context-restore`.

---

## Gates

| Where | Gate | Cleared by |
|---|---|---|
| Session 1.1 | Install-behavior change | Human nod (low stakes, reversible). |
| Session 5.2 | Rewriting the standing dev-time-only rule | Explicit ratification + `DECISIONS.md` entry. |
| Sessions 19–20 | Choice of the second consumer | Human selects the project. |

---

## Living-plan note

This plan is a record, not reality. Each session reconciles it against the repo
and against `feedback.jsonl`. When the harvest disagrees with the planned order,
the harvest wins — surface the divergence, re-sort, and log it. The 5–20 session
range is honored: Sessions 1–6 are the minimum viable arc (loop running, identity
resolved); Sessions 7–24 are the feedback-driven remainder (Phase 3.5 inserted
2026-05-24, extending the original 20-session arc).

---

## Next horizon — post-Phase-5 sketches (2026-05-26)

After the LOOP_V0 observability work + auto-ingest watcher + decisions tab landed,
four directions are queued. Each is a sketch — what's the *smallest experiment*
that would tell us whether it's worth building?

### N1 — Sidebar UX deepening

**Goal:** When a node is selected, the sidebar should answer "what was this and
what did it lead to?" without scrolling through Outgoing/Incoming slug lists.
**Smallest experiment:** For `stage` nodes, render a compact 1-line summary
(worker + status + tool result key fact, e.g. *"Retrieve — passed — 10 neighbors,
top: arxiv 2605.17662"*). Pull from the iteration's `narration_log` + the LLM
call's `prompt_messages[-1].content[tool_role]` already in the brain. If the
1-liner is sufficient on iter-008 (the canary), defer the larger redesign.
**Reversibility:** trivial — sidebar render in `graph.html` only.

### N2 — Verify the proposal/feedback loop is *actually* closing

**Goal:** The chain is `harvest finding → propose → review-proposal verdict →
implementation → updated rules/skills`. Today the only evidence the loop closes
is anecdotal: P-005 and P-007 were closed manually this session, P-001/002/003
back in S15. We have not measured: how many open proposals stagnate? Are
auto-rejects actually rule-grounded? Does an accepted proposal lead to a code
change within N sessions?
**Smallest experiment:** Add a tiny report — `scripts/proposal_health.py` —
that prints, per proposal: filed-at, days-open, verdict (if any), and (for
accepted) whether a commit referenced its `proposal_id` in the message. Run it
once; flag any stalled / unverified entries. If the report surfaces real gaps,
build the harvest → proposal automation; if everything's clean, leave the loop
manual.
**Reversibility:** trivial — read-only script.

### N3 — Framework piping into the things it spawns

**Goal:** Today the framework helps Derrick build apparatuses. The next step is
for the framework's *spawn-contract* + runtime-safe core to actually govern an
autonomous child agent dispatched from the apparatus side. Right now
`spawn.jsonl` only carries dev-time SP-001..003 entries (per CLAUDE.md
boundary). The runtime path is documented but unexercised.
**Smallest experiment:** From `a_bgt_rsi`, have Nara file ONE spawn-contract
entry for a single LOOP_V0 worker call (e.g. `retrieve_literature`), then run
it under the contract — done-condition, authority cap, budget. Spawn ledger
entry lands in the brain (read by ingest); the iteration's stage node links to
the spawn page. Validates the contract → child → reconciliation → graph flow
end to end with no behavior change to the apparatus.
**Reversibility:** medium — apparatus-side change in `orchestrator/nara.py`,
revertable but needs care so the contract write isn't accidentally read by
brain code (firewall).

### N4 — Measurable brain improvement over time

**Goal:** The Phase 3.5 kill-switch was "≤1 file opened to reconstruct a day's
activity (vs 6+ before)." We hit that, but it was a one-shot win. The harder
question: does the brain *get smarter* — i.e. do active rules + accepted
proposals + harvest findings compound, making each subsequent session need less
remembering? Without a metric, we can't tell.
**Smallest experiment:** At the start of every session, the resume-state /
context-restore skill already surfaces active corrections. Add a 3-number
snapshot to the briefing: (a) active-rules count, (b) days since last
human-review proposal closed, (c) median time-to-resume (clock from session
start to first run-log entry). Track over 5 sessions; if (a) grows and (c)
shrinks, the brain is compounding. If not, dig in.
**Reversibility:** trivial — read-only snapshot inside an existing skill.

These are not Sessions yet — they're hypotheses worth small experiments. When
one passes its smallest-experiment bar, lift it into a numbered Session below
**Sessions** with a falsifiable success criterion.
