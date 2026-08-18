# Decisions Log

Append-only, date-stamped record of decisions and corrections. **Never rewrite or
delete entries** — add new ones. Newest at the bottom. Each entry follows the
decision-log skill: decision, alternatives, rationale, reversibility, supersedes.

Format:

```
## YYYY-MM-DD — <short title>
**Decision:** ...
**Alternatives:** ...
**Rationale:** ...
**Reversibility:** trivial | easy | medium | hard — <cost of undoing>
**Supersedes:** <date/title, or "none">
```

---

## 2026-05-18 — Agent system scaffolded
**Decision:** Created a portable agent framework (skills + file memory) authored
to the Agent Skills standard, runnable in both Pi and Claude Code via symlinks.
Adopted a curated, research-tuned subset of gstack rather than the full
product-oriented framework.
**Why:** Target harness is Pi; current harness is Claude Code; the project
(`autoresearch`) is an ML/research pipeline with no product-UI dimension, so
gstack's CEO/design/QA-browser roles do not apply.
**Supersedes:** none

## 2026-05-18 — Added execution-discipline skills
**Decision:** Added 4 skills — `gate-check`, `validate`, `run-log`,
`resume-state` — and adapted `experiment` (autonomous loop section) and
`plan-research` (design-vs-execute pointer).
**Why:** Explored the primary consumer `/home/decross1/projects/a_bgt_rsi` — a
contract-governed, plan-driven research program (authoritative `plan.yaml`,
state-file resume, blocking human gates, JSONL run log, validations never
coerced). The original gstack-derived skills were a design/ship loop and did
not cover plan-execution discipline, which is this project's core need. The
gstack safety roles (`/careful`/`/freeze`/`/guard`) dropped on 2026-05-18 are,
reframed, exactly this gap. Skills stay general-purpose.
**Supersedes:** partially revises the 2026-05-18 scaffold decision's skill set.

## 2026-05-18 — Scope boundary: dev-time vs project-runtime
**Decision:** Established that this framework is a dev-time harness only; its
skills must not be loaded into any project's runtime agent. Added `BOUNDARY.md`
and a `## Scope boundary` section to `AGENTS.md` / `README.md`.
**Why:** Explored `a_bgt_rsi`'s architecture — its runtime orchestrator (Gemma 4
+ OpenClaw + NemoClaw) also runs on Pi. With the dev skills installed globally
in `~/.pi/agent/skills/`, the apparatus runtime could inherit them. The two
"orchestrators" (dev-time and apparatus-runtime) must stay separate.
**Supersedes:** none

## 2026-05-21 — Correction: the lead consumer is `a_bgt_rsi`, not `autoresearch`
**Decision:** The 2026-05-18 "Agent system scaffolded" entry names the consumer
project `autoresearch`. That is incorrect: `autoresearch` is a third-party repo
cloned *inside* `a_bgt_rsi` (`a_bgt_rsi/clones/autoresearch`). The framework's
lead consumer is `/home/decross1/projects/a_bgt_rsi`.
**Why:** This log is append-only; the original entry cannot be rewritten. This
entry corrects the record.
**Supersedes:** corrects — does not supersede — the project name in the
2026-05-18 "Agent system scaffolded" entry.

## 2026-05-21 — Framework re-scoped: agnostic, self-hosted, runtime-safe core
**Decision:** The framework is re-scoped from an ML/research-tuned toolkit to an
*agnostic* framework for disciplined agentic development and autonomously spawned
agents, usable by any system. `a_bgt_rsi` remains the lead consumer that informs
it. Three structural commitments, ratified in `plan.md` (v1):
1. **Dogfooded** — the framework's own development runs as a plan-driven project
   using its own skills (`plan.md` + `run_state/framework.state.json` +
   `run_state/framework.run.jsonl`).
2. **Read-only feedback** — a `harvest` skill scores each skill against
   `a_bgt_rsi`'s execution trace into `memory/feedback.jsonl`; `a_bgt_rsi` itself
   is never modified.
3. **Runtime-safe core** — a subset of Layer-A skills will become embeddable in
   spawned/runtime agents; `BOUNDARY.md`'s blanket dev-time-only ban becomes a
   layering rule (scheduled for Session 5).
**Why:** The framework was a high-fidelity mirror of one project's discipline but
had no falsifiable claim about its own value, no feedback loop, and a
"research-tuned" identity that contradicted the goal of general use. `plan.md`
gives it a charter, metrics, decision rules, and a 20-session improvement arc.
**Supersedes:** revises the scope of the 2026-05-18 "Agent system scaffolded"
decision. The 2026-05-18 "Scope boundary" decision stands until Session 5
formally rewrites `BOUNDARY.md`.

## 2026-05-21 — BOUNDARY.md rewritten as a layering rule; runtime-safe core established
**Decision:** `BOUNDARY.md`'s blanket "all skills are dev-time only" rule is
replaced by a two-class layering rule: **dev-only skills** (Layers B and C) that
must never enter a project's runtime agent, and a **runtime-safe core** (the 5
Layer-A skills — `resume-state`, `gate-check`, `validate`, `run-log`,
`fallback`) that may be *deliberately* embedded in a spawned / runtime agent.
`BOUNDARY.md` now defines the `runtime-safe` contract: no assumed human, no
dev-harness dependency, minimal context cost, no surprising side effects, a
closed dependency set. Per-skill conformance to that contract is verified in
Phase 3.
**Why:** The framework's goal (2026-05-21 re-scope) is to serve autonomously
spawned agents in any system, not only dev-time sessions. A blanket ban made the
framework's most general, most valuable asset — the execution-discipline core —
unusable where it is most needed. The dev-time/runtime line did not move; it
sharpened from "all skills" to "the dev-only layers."
**Supersedes:** the blanket rule of the 2026-05-18 "Scope boundary: dev-time vs
project-runtime" decision. The dev-time/runtime *distinction* that decision drew
still stands.
**Gate:** this decision reverses a standing rule; ratified by explicit human
go-ahead, 2026-05-21.

## 2026-05-24 — Treat 100% metrics in small-N tests as suspicious-clean
**Decision:** When a research metric reads exactly 100% (or 0%) on a small-N
test driven by a strongly-directive prompt, do not treat the result as
evidence of robustness. Investigate the prompt and the N before adopting.
**Correction:** Default to disbelieving small-N clean reads; raise N or
soften the prompt before trusting.
**Alternatives:** (a) trust the metric and ship — rejected, this is how
prior-driven results get over-claimed (cf. D-028 cooperation lock-in is a
Gemma 4 prior); (b) widen the test set silently — rejected, hides the
methodological constraint.
**Rationale:** Day-4 tool_call_invocation_rate=1.00 on the e2e set (see
brain page `anomaly-tool-call-100pct`) was driven by a system prompt
mandating tool use. A 100% metric on a small N with a strong directive
prompt is structurally biased upward, not a robustness signal.
**Reversibility:** trivial — single-line rule of practice, no infra
implication.
**Supersedes:** none

## 2026-05-24 — Reconcile state-file lag against run-log during gate-armed periods
**Decision:** When `resume-state` finds the state file's
`completed_tasks` shorter than the run log's completed entries across a
gate-armed window, treat the run log as canonical for the held period.
Walk it to determine what is done; do not re-run completed work based on
the lagging state.
**Correction:** Trust the run log over the state file when they disagree
across a gate-armed period.
**Alternatives:** (a) require write-through to state during holds —
rejected, makes the "held but working" state ambiguous (state in a hold
should be a record of the hold, not a mutable buffer); (b) leave the
behavior project-specific — rejected, leaves a real resume-during-hold
recovery failure mode unguarded across projects.
**Rationale:** H006 finding in `a_bgt_rsi` `week1.run.jsonl` L137 — 16
day_7 task IDs were backfilled into `state.completed_tasks` AFTER the
publication-review gate cleared at L136. During the gate-armed window
(L125 onward), the run log had the tasks; the state file did not. A
session that crashed and resumed during the hold would have either
re-run completed work (trusting state) or invented an ad-hoc
reconciliation; making the run log canonical for held periods is what
the consumer did manually and is the rule we encode now.
**Reversibility:** trivial — single-paragraph protocol clarification in
`resume-state` SKILL.md; the rule of practice itself is the durable
artifact, regenerated into `rules.md` as FR-002 by `regen_rules.py`.
**Supersedes:** none — extends [[resume-state]] step 5.

## 2026-05-24 — Defer S19-S20 uplift test pending consumer choice
**Decision:** Defer the Phase-4 uplift test (S19-S20: onboard a second,
less-disciplined consumer, run it with and without the runtime-safe core,
measure audit-completeness uplift). No consumer is being chosen at this
time; the gate `s19_choose_uplift_consumer` clears as
*deferred-by-human-choice*. Advance to S21 (Phase 5).
**Alternatives considered:**
(a) Spin up a toy `latency-probe` project — rejected for now: no immediate
    appetite, and a toy's realism is bounded.
(b) Spin up a toy RAG eval harness — rejected for now: same reasoning.
(c) Adopt an existing real project — rejected for now: no named candidate;
    higher scope risk than a toy without proportional payoff today.
(d) Proceed to Phase 5 (S21+) — **chosen.**
**Rationale:** The Charter's uplift claim is structurally testable only
with a less-disciplined second consumer; doing it well requires
deliberate setup that the user is not ready to commit to today. Phase 5
(autonomous spawned agents) does not depend on uplift evidence being
gathered first. The deferral is recorded so v1.0 (S24) can be honest
that uplift remains untested — or so a future session can pick it up.
**Reversibility:** trivial — return to S19 when a consumer is named;
all S19-S20 plan content remains in `plan.md`.
**Supersedes:** none.

## 2026-05-26 — Brain UI: stage projection model (collapse dispatch+receipt+call per worker)
**Decision:** In `scripts/project_pages.py::synthesize_stages`, collapse each
`(iteration, tool)` triple — `loop_v0_tool_dispatch` event + `loop_v0_tool_receipt`
event + the vLLM call they wrap — into one synthetic **`stage`** node per worker.
Stage entities live only in `graph_data.js` / `pages/`; the underlying narratives
and edges in `narratives.jsonl` / `edges.jsonl` are untouched. Stages get a
per-worker color (Hypothesize/Retrieve/Novelty/Critique/Journal) so the per-
iteration pipeline reads at a glance.
**Alternatives considered:**
(a) Hide mechanical nodes entirely via filter — rejected: lineage debugging
    becomes impossible.
(b) Emit stages into `edges.jsonl` + a new narrative type — rejected: pollutes
    the canonical append-only ledger with derived data; re-projection would
    require schema versioning.
(c) Defer to per-iteration markdown rendering (no graph nodes) — rejected:
    loses the cross-iteration comparability that the graph affords.
**Rationale:** The user's "I can't tell what is doing what" feedback was about
the graph being 78% mechanical noise. Stages are a *view* over the raw data —
turning them on/off is a UI concern, not a data concern. Keeping the synthesis
in `project_pages.py` keeps `edges.jsonl` clean (only narrate / ingest emit
there) and means we can change the stage model without migrating data.
**Reversibility:** trivial — delete `synthesize_stages()` and the edge filter
in `project_pages.py::main()`. Brain reverts to the iter+event+call view.
**Supersedes:** none.

## 2026-05-26 — Brain UI: decisions removed from graph by default; dedicated tab
**Decision:** `decision` type moves out of the **Research** filter group into a
new **History** group with `defaultOn: false`. The graph default-hides all 40
decision nodes. The sidebar gains a **Decisions** tab listing them newest-first
with framework/apparatus side badge, clicking a row renders the full decision
page in the panel. Decision nodes remain in `DATA.nodes` so cross-reference
edges (correction `references` decision) still resolve when followed from
another node's sidebar.
**Alternatives considered:**
(a) Drop decisions from `graph_data.js` entirely — rejected: breaks
    correction→decision navigation.
(b) Keep decisions in Research filter group, default on — rejected: 40 decision
    nodes dominate a graph designed for iteration walking.
(c) Show decisions only when a correction is selected — rejected: too clever,
    surprising UX.
**Rationale:** Decisions are durable history, not active research. A flat
chronological list is the right interaction (`What did we decide on date X?`)
— the graph adds nothing. Keeping them in `DATA.nodes` preserves brain
integrity (every page is graphable on demand) without committing to drawing
them all every render.
**Reversibility:** trivial — move `decision` back into `FILTER_GROUPS.research`
in `graph.html`. The tab survives the change as a bonus access path.
**Supersedes:** none.

## 2026-05-26 — Brain auto-ingest: file watcher daemon over cron
**Decision:** `scripts/watch_brain.py` is a pure-stdlib polling daemon
(`scripts/watch_brain.sh` lifecycle wrapper, mirrors `serve_brain.sh`). It
polls `a_bgt_rsi/{run_state,memory,logs}/*.jsonl` mtime+size every 1s, debounces
1.5s after the last change, then fires `ingest_apparatus.py → project_pages.py
→ render_brain.py`. ~3s end-to-end latency from apparatus write to graph
update.
**Alternatives considered:**
(a) cron every 5min (P-007's original suggestion) — rejected: 5-min lag is too
    long for the "is anything running right now?" question, AND 95% of cron
    fires are no-ops (wasted invocations).
(b) Apparatus-side post-iteration hook — rejected: violates the brain firewall
    (apparatus would have to know about the brain).
(c) inotify / `watchfiles` dep — rejected: extra runtime dependency for a use
    case that pure-stdlib handles fine.
(d) systemd path unit — rejected: ties to a specific init system; less portable
    than a shell-wrapped Python process with pidfile + log.
**Rationale:** File-first + write-only-on-apparatus rails are non-negotiable.
The watcher reads apparatus JSONL only, never writes back. Polling is "slower"
than inotify but invisible at the human-feedback latency scale (~3s vs ~1s).
Idempotent pipeline + (file,line) dedup makes spurious wakeups cheap.
**Reversibility:** trivial — `scripts/watch_brain.sh stop` and remove the two
files. Brain returns to manual `ingest -> project -> render` runs.
**Supersedes:** none.

## 2026-05-27 — run-log schema: agent (required) and skill_used (optional)
**Correction:** Extend the canonical run-log entry shape with two new fields:
`agent` (required) — the entity that ran the step (e.g. `nara`,
`claude-code-main`, `human:<id>`); and `skill_used` (optional) — the framework
skill this step is part of (e.g. `validate`, `fallback`), present only when
the entry is a skill invocation. Anonymous-by-task-id logs prevent the brain
from attributing skill use to a specific actor, which breaks the
`harvest → propose → rule` self-improvement loop the framework exists to run.
Existing entries (137 framework + 281 consumer) are unrewritten — append-only
honored — and projected via per-file canonicalization at read time
(`framework.run.jsonl` → claude-code-main, `week1.run.jsonl` → nara, etc.).
**Alternatives considered:**
(a) Add a new runtime-safe `trace` skill alongside run-log — rejected: more
    surface area, no real benefit over evolving the existing skill.
(b) Filename-only heuristic, no schema change — rejected (this session's
    user choice): enshrines an inference layer that breaks when apparatus
    moves files; the heuristic should be a backward-compat fallback, not
    the steady state.
**Rationale:** `run-log` is already the runtime-safe Layer-A skill called on
every consequential step. Carrying agent in the entry shape closes the gap
in one place, vs. spreading the concern across N consumer-side adapters.
`skill_used` is optional because not every step is a skill phase — task
completion records that aren't tied to a specific skill omit it cleanly.
**Reversibility:** medium — the schema is backward-compatible (existing
entries without `agent` keep working via the projector's filename
canonicalization). Hardest part to undo is the convention shift in newly
authored run-log entries; revert would mean asking consumers to drop the
field again, which is mild churn but not data loss.
**Supersedes:** none — extends the [[run-log]] entry shape that was last
hardened in S10.

## 2026-06-10 — Two-surface observability design system (UI overhaul)

**Decision.** (1) Two surfaces, one design language: apparatus :5173 = runtime
ops + escalation inbox hero; brain :5174 = governance (file-first static).
Shared token block byte-mirrored in both repos, enforced by
`scripts/check_design_tokens.py` (framework reads consumer — firewall-correct
direction). (2) The brain graph is re-scoped from whole-brain event hairball to
an **agent↔skill cluster map**: packs as hulls, usage-weighted edges
(solid=explicit `skill_used`, dashed=inferred via the attribution ladder),
governance painted on nodes (drift halo / healed pulse / fresh outline /
by-design muted / runtime-safe ring); event lineage is a scoped ego-mode
(≤2 hops), not a destination. (3) Escalation is severity×reversibility-tiered
(state_gate > stale_run > gate/finding review > bubble-info) with one-decision
cards; copy-paste CLI demoted to fallback once D-046 in-UI attestation is live.

**Alternatives.** Unify both UIs into the React app (rejected: breaks brain
file-first doctrine, burns budget on migration); keep the force-directed
whole-brain graph as a co-equal view (rejected by user: wrong medium for
overview — structure views carry overview, graphs carry relationships);
replace node-link entirely with matrix/timeline (rejected: loses the
agent↔skill relationship medium the user explicitly wanted).

**Rationale.** Research synthesis (overview-first/details-on-demand, 5–9
element ceiling, RAG reserved for state, color-as-identity per agent,
graph-for-structure vs timeline-for-time) + judged mockup competition
(m1 stack won 24/25 on identical data; SPEC.md is the build contract).

**Reversibility.** Medium — static pages + generators are replaceable;
schema v2 of summary.json is the load-bearing contract (consumers: both
dashboard pages, verify_brain_view).

## 2026-06-13 — Housekeeping: reconcile the 2026-06-10 UI move (state write-forward)

**Decision.** Close out the 2026-06-10 two-surface UI overhaul as drift cleanup:
(1) write the run log forward into `framework.state.json` — append the six
`ui_overhaul_*` tasks (run log L138–143, all `passed`) to `completed_tasks` and
refresh `value_metrics`; `current_session` stays 24 (the overhaul was out-of-band
work, not a numbered plan session). (2) Retire stale `graph_data.js` references in
`project_summary.py` / `project_pages.py` (file deleted in the overhaul; data now
lives in `summary.json` / `summary_data.js` / `map_data.js`). (3) Point
`serve_brain.sh` at `dashboard.html` (the post-overhaul primary surface, not
`graph.html`) and correct the `watch_brain.{py,sh}` pipeline docstrings to the real
five steps (ingest → project_pages → project_map → project_summary → render).
(4) Remove the merged `brain-overhaul` worktree + branch. Found and verified by an
adversarial discover→verify→critic workflow (18 confirm / 6 needs-human / 6 reject).

**Correction:** When a state file lags the run log across a shipped-but-unrecorded
work burst, write the state forward from the run log rather than leaving the lag —
the run log is canonical (per the 2026-05-24 correction), and resume-state's
write-through is the prescribed reconciliation, not an optional nicety.

**Alternatives.** Leave the state lag and rely on resume-state's run-log
reconciliation each session (rejected: the divergence re-surfaces every resume and
invites re-running done work); bump `current_session` past 24 (rejected: the
overhaul wasn't a numbered session — would misnumber the plan).

**Rationale.** The 442-file projection churn + state lag + stale UI docs were the
visible drift from shipping the overhaul without a closing reconciliation pass.
Recording it keeps the audit trail honest and the next resume clean.

**Reversibility.** High — all edits are doc/comment/state-record changes; no code
behavior changed; the four verifiers (verify_brain_view, doc-counts,
design-tokens, pi-discovery) gate the result.
**Supersedes:** none — extends the 2026-06-10 design-system entry above.

## 2026-06-15 — Dynamic proposal-review brain: localhost LLM-assisted review UI

**Correction:** The brain's proposal-review loop becomes *dynamic*. Until now
review was a static file read + a manual verdict; the new backend
(`scripts/brain_server.py`, stdlib `ThreadingHTTPServer` on 127.0.0.1:5180)
serves the file-first brain view AND a JSON API that lets a human *discuss and
amend* a proposal with a local LLM (Gemma 4 at `127.0.0.1:8000`, OpenAI-compatible
chat) before deciding — then accept / reject / request-revision, or export a
dev-agent handoff, all from one localhost surface. This mirrors the a_bgt_rsi
**D-046** human-write-back pattern exactly: the UI's verdict buttons POST to an
endpoint that **execs the blessed CLI via argv** (`scripts/review_proposal_cli.py`,
no shell), the verdict enum is frozen (`accept|reject|needs_revision`), the write
is append-only with a `human:ui` actor stamp, and out-of-enum / bad input exits
nonzero and **writes nothing** (fail-closed). A human accept on a skill/rule
proposal IS the human-review *authority* path of `review-proposal`; agents keep
the auto-reject fast-path. The verdict CLI records the verdict only — it does not
enact the change; enacting a skill/rule edit remains a separate dev-session /
handoff step.

**Two invariants are load-bearing and ratified here:**
- *Firewall.* This backend is **dev-time only**, bound to `127.0.0.1`, and must
  never be inherited into an apparatus runtime (BOUNDARY.md). It is a drafting +
  governance surface for the framework's own self-improvement, not a runtime
  service. The brain firewall verification (`install.sh --verify-firewall`) is
  unchanged and still holds.
- *Determinism.* Files remain canonical. Gemma is a **drafting assistant only** —
  every LLM output (review cards, discussion turns) is persisted append-only to
  `memory/brain/proposal_cards.jsonl`. Projection / regeneration of the brain
  pages and view data **never calls the LLM**; it reads the persisted files. The
  brain stays deterministically reconstructible from its ledgers.

**Alternatives considered:**
(a) Keep review static — read the proposal page, decide via the terminal CLI —
    (rejected: the manual flow has no place to *amend* a half-formed draft into a
    decidable proposal; the discuss→amend loop is the whole point, and the file
    record loses the reasoning that produced the verdict).
(b) Let the LLM write verdicts / enact edits directly (rejected: violates the
    D-046 blessed-CLI contract and the human-review authority path — the human
    decides, the LLM only drafts; an LLM with write authority is a firewall and
    provenance hole).
(c) Have projection re-summarize proposals with the LLM at render time (rejected:
    breaks determinism — the brain would no longer be reconstructible from files
    alone, and renders would be nondeterministic and network-dependent).
(d) Expose the backend beyond loopback for remote review (rejected: dev-time-only
    tooling on 127.0.0.1 keeps it firmly outside any runtime/network surface).

**Rationale:** The proposal loop is the framework's self-improvement engine; its
friction was the lack of an interactive *amend-then-decide* surface. A localhost,
LLM-assisted UI that drafts-into-files and writes verdicts only through the blessed
CLI gives frictionless review without surrendering the two things that make the
brain trustworthy — the human-write-back firewall and file-canonical determinism.

**Reversibility.** High — the backend is an additive stdlib server over existing
canonical files; stop it and review falls back to the static view + terminal
`review_proposal_cli.py`. `proposal_cards.jsonl` is append-only LLM-draft cache
and can be discarded without losing any governed verdict (those live in
`proposals.jsonl`). No skill contract or file schema is rewritten.

**Supersedes:** none — extends the brain-UI scope work (the 2026-06-10
two-surface design-system entry and the a_bgt_rsi D-046 write-back contract it
references).

## 2026-06-15 — Brain view projections are git-ignored build artifacts (P-013 resolved)

**Correction:** The brain's view projections are **generated build artifacts, not
source, and are not git-tracked.** Untracked: `memory/brain/pages/*.md`,
`memory/brain/view/{map_data.js, summary.json, summary_data.js, index.json}`, and
the per-day `memory/brain/view/<YYYY-MM-DD>.md` views. They are rebuilt
deterministically from the canonical ledgers by `scripts/regen_brain.sh` (the same
four steps `watch_brain.py` runs: project_pages → project_map → project_summary →
render_brain).

**Canonical (stays tracked):** the ledgers (`narratives.jsonl`, `edges.jsonl`,
`proposals.jsonl`, `feedback.jsonl`, the run logs, `DECISIONS.md`), the projector
scripts, and the hand-written view assets (`*.html`, `map.js`, `ui.js`,
`tokens.css`, `mockups/`).

**Why:** every ledger change re-projected ~920 pages + the summary/map data, so each
commit dragged hundreds-to-thousands of churn lines and `verify_brain_view`
cross-checks went stale-on-checkout whenever a commit excluded the regenerated
artifacts. Treating projections as build output removes the churn entirely and makes
the tree honestly reflect source.

**Alternatives considered:**
(a) Keep tracking them and commit the regen with every ledger change — rejected: the
    2.9k-line churn per commit is noise and made `verify` a coin-flip depending on
    whether regen was bundled.
(b) Track only the aggregates (summary/map) but not pages — rejected: half-measure;
    the aggregates churn too, and a split policy is harder to reason about.

**Reversibility.** High — re-track with `git add -f` and drop the `.gitignore`
lines. No ledger or schema change; the projections are fully reproducible from the
tracked sources via `scripts/regen_brain.sh`.

**Supersedes:** none — resolves proposal P-013. `verify_brain_view` now skips the
projection checks when the artifacts are absent (fresh checkout) and validates them
when present (after regen).

## 2026-06-16 — Brain server defaults to 0.0.0.0 (LAN-reachable) instead of loopback

**Decision:** `scripts/serve_brain.sh` now defaults `BIND` to `0.0.0.0` (was
`127.0.0.1`). A fresh `serve_brain.sh start` is reachable from the user's other
machines (e.g. `http://10.0.0.73:5180/proposal_review.html`) without the per-start
`BRAIN_BIND=0.0.0.0` override that had been required. Loopback-only is still one
flag away: `BRAIN_BIND=127.0.0.1` (env) or `--bind 127.0.0.1`.

**Why:** the dynamic proposal-review brain is used from a second machine on the
home LAN; defaulting to loopback meant every start needed an override and a missed
override silently produced an unreachable server (the "site can't be reached"
symptom seen 2026-06-15).

**Accepted tradeoff (security posture).** Binding `0.0.0.0` exposes the write-back
API to the LAN. That path is **not** an arbitrary-write surface: the UI only POSTs
to blessed CLIs (`review_proposal_cli.py`) via argv (no shell), against a frozen
verdict/basis enum, stamped `human:ui`, append-only — an out-of-enum value exits
nonzero and writes nothing (the D-046 pattern). Exposure is scoped to a trusted
home LAN; public/internet exposure remains explicitly the user's call and is not
enabled by this default.

**Reversibility.** High — one-line revert of the default, or set
`BRAIN_BIND=127.0.0.1` at start. No schema/ledger change.

**Supersedes:** none — operational config; complements the D-046 write-back
contract referenced above.

## 2026-06-28 — North star: a framework that audits and heals its own discipline

**Decision:** The framework's working north star is reframed from the Charter's
*uplift* test (prove the runtime-safe core makes a **less-disciplined** consumer
produce an audit trail it otherwise would not — Sessions 19–20) to **"a framework
that audits and heals its own discipline."** The measure of progress becomes
whether the self-improvement / self-healing loop (harvest → drift → draft → review
→ enacted) observably closes on the framework's *own* skills, with no agent ever
silently editing a skill or rule.

**Alternatives considered:**
(a) Keep uplift as the headline claim and run S19–S20 first — rejected for now: no
    second consumer is chosen or wanted; uplift has been deferred since 2026-05-24,
    and the self-healing direction is where the work and the value have actually
    accrued (dynamic review brain, live surfaces, drift→draft loop).
(b) Delete the uplift claim outright — rejected: it is a real falsifiable claim and
    the Charter is append-only history; deferring is honest, deleting is not.
(c) Treat self-healing as a side-quest under Phase 5/6 — rejected: it is now the
    primary direction and earns its own phase and falsifiable session (Phase 7 /
    S26 in `plan.md`).

**Rationale:** The framework already records how its skills are used (feedback,
drift, decisions, rules); the highest-leverage next step is to make that record
*act* — surface drift, bubble candidates, route by blast radius, let a human heal
the skill — rather than stand up a second consumer to measure uplift. Fidelity is
partly evidenced; uplift stays on the books, deferred.

**Reversibility:** easy — this is a prioritization, not a deletion. S19–S20 remain
in `plan.md`; returning to the uplift test is a re-sort away.

**Supersedes:** none — reprioritizes (does not revoke) the Charter's two-claim
structure and extends the 2026-05-24 "Defer S19-S20" decision.

## 2026-06-28 — Reconcile the audit trail: record the self-healing / live-UI burst

**Correction:** When the recorded state (state file, run log, plan, and the derived
`rules.md`) lags shipped git reality across an out-of-band work burst, reconcile by
writing all of them forward from the commits — the same write-forward the
2026-06-13 housekeeping correction prescribes (FR-004), applied now to a larger,
longer-lived divergence. Do not leave the lag for the next resume to re-discover.

**What was reconciled.** At session start (2026-06-28) the state file (last written
Jun 15, `current_session` 25) lagged reality by ~13 days and a whole subsystem:
- the run log held 3 completed tasks the state file never absorbed
  (`s25_proposal_review_ux_v2`, `s25_v3_accept_note_ux`, `p013_untrack_brain_projections`);
- git held 10 commits (Jun 16–18) in neither the run log nor the state file nor
  `plan.md`: the **self-healing loop** (`scan_drift` / `blast_radius` /
  `graduate_drafts` / `draft_proposals`, drift→draft bubbling, honest-loop
  dashboard, +9 test files), the **live dashboard / cluster-map** (`GET /api/summary`,
  `/api/map`, 30s poll), and the **skill-signals handoff** reconciled with
  `a_bgt_rsi`'s **D-056** review — only the 2026-06-16 bind change had a decision
  entry;
- `rules.md` showed 3 active rules while DECISIONS.md held 6 (`regen_rules.py` was
  never re-run after the June corrections); `conformance.md` was stale (37 vs 64
  findings);
- two canonical brain ledgers (`narratives.jsonl` +1335, `edges.jsonl` +475) carried
  uncommitted auto-ingested apparatus events (Jun 19–25) from the watch daemon.

**Actions.** Regenerated `rules.md`; added **Phase 7 / Session 26** to `plan.md`
recording the self-healing loop with a falsifiable pass-signal + kill-switch and the
two priming misfires found (the `scan_drift` verdict false-positive; the
`draft_proposals` resolved-finding gap); backfilled run-log entries for the burst;
wrote `framework.state.json` forward (completed tasks + Session 26, `current_session`
26, refreshed `value_metrics`); committed the pending ledger appends. `conformance.md`
is NOT mechanically regenerable (it is harvest-updated) and is left flagged for the
next harvest pass — also due (watermark at a_bgt_rsi L1541 / D-052, but D-056 is
already in play).

**Alternatives considered:**
(a) Housekeeping-only, `current_session` stays 25 (the 2026-06-13 framing) — rejected:
    the self-healing loop is now the north-star direction (this date's other entry),
    so it earns a numbered Session, not a footnote.
(b) Backfill per-commit run-log entries at their original Jun-17/18 timestamps —
    rejected: the run log records *observed* steps; these entries are stamped at the
    reconciliation (2026-06-28) and name the originating commit + date in-body.

**Rationale:** A self-healing loop cannot be lit up honestly while the framework's
own recorded state is itself drifted — the reconciliation is the prerequisite for
S26. Recording it keeps the audit trail truthful and the next resume clean.

**Reversibility:** high — all edits are record / derived-artifact / state changes; no
skill contract or file schema changed. `rules.md` is regenerable; the state/run-log
write-forward is the prescribed reconciliation, not a rewrite of history (DECISIONS
and the run log remain append-only).

**Supersedes:** none — extends the 2026-06-13 housekeeping correction (FR-004) and
the 2026-05-24 run-log-canonical correction (FR-002).

## 2026-06-28 — Self-healing drift semantics: a run-log outcome is never drift (Option 3)

**Correction:** Machine drift detection treats drift as coming from TWO trustworthy
sources only — the apparatus *deliberately self-reporting* misuse/friction/gap
(source="runtime") and FR-003 *schema violations* in the framework's own run log.
A run-log *outcome* is NEVER inferred as skill drift. A verdict-rendering skill
honestly returning 'failed' (validate refusing to coerce a near-miss; gate-check
halting; repro-check failing a check; code-review rejecting a diff) — or any skill
recording aborted/escalated — is usually the skill WORKING, not malfunctioning, so
inferring drift from a step's status produces only false positives.

**Also:** the bubbler (`draft_proposals.py`) never files a draft whose remedy has
already shipped — it skips a finding that proposes a *new skill that now exists*
(e.g. decision-log, slip-ladder) and a finding that a *later harvest confirmed
clean* on the same skill (the conformance / 2-clean-harvests evidence supersedes the
older friction/gap). Both guards are permanent-safe: a finding with no later
confirmation, or one newer than the last confirmation, still bubbles.

**Why:** priming the loop on 2026-06-28 showed the original `runlog_failure` detector
would have emitted its first-ever signals AGAINST validate for doing its job (honest
FAIL verdicts on `lit_battery_post_t1_final` / `d050-decision-run` read as drift). A
self-healing loop that misreads healthy discipline as drift is worse than no loop.
Option 3 makes every signal the loop emits trustworthy from day one — the condition
for turning `BRAIN_AUTODRIFT` on by default.

**Result:** `scan_drift.runlog_failure` is RETIRED (defined-but-uncalled seam);
`drift_signals.jsonl` is honestly empty (no schema violations, no self-reports yet);
8 open-backlog findings bubbled as DRAFT candidates (ship, resume-state, orchestrate,
experiment, repro-check, fallback); 10 skipped (8 superseded, 2 already-shipped), all
reported, not silent. `BRAIN_AUTODRIFT` now defaults on (set `=0` to disable).

**Alternatives considered:**
(a) Option 1 — exclude failed/partial_pass only for the four verdict skills
    (rejected: leaves the outcome heuristic noisy for ship/fallback/etc.).
(b) Option 2 — flag only aborted/escalated/halted (non-completion) for all skills
    (rejected: a non-completion is usually the skill correctly halting/aborting —
    still a low-signal proxy that would re-introduce false positives).
(c) Option 3 — trust deliberate self-reports + schema violations only (chosen).

**Reversibility:** high — re-enable `runlog_failure` in `scan_drift.build_signals()`;
drop the two bubbler guards; set the `BRAIN_AUTODRIFT` default back to off. No ledger
or schema change; the 8 drafts are status=draft and discardable via review.

**Supersedes:** none — implements the 2026-06-28 north-star pivot (Phase 7 / S26).

## 2026-06-28 — Self-healing light-up: adversarial-audit corrections

**Correction:** Scope a trustworthiness claim to the lane actually verified, and
compute "clean" honestly. An independent auditor (run against commits c878afe +
d8d93ef) found the light-up sound on safety (determinism, firewall, append-only,
nothing auto-enacts) but over-reaching on two points, both fixed here:

1. **Supersession over-suppression (a real bug).** The bubbler's
   `last_confirmed_harvest` equated "a 'confirmed' finding exists at harvest H_n"
   with "the skill is clean at H_n" — but a harvest can BOTH confirm and re-open a
   skill (fallback, repro-check at H008). The guard therefore suppressed two
   still-OPEN findings (fallback H002, repro-check H003 — both listed open in
   `conformance.md` / `value_metrics.skills_open`) with the *false* reason
   "confirmed clean at H008". Replaced with `last_clean_harvest`: a harvest is
   clean for a skill only if it confirms it AND carries no open finding on it. The
   two findings now bubble correctly (P-027, P-029) and the printed reasons are
   accurate.

2. **Overstated trustworthiness.** The d8d93ef framing "every signal trustworthy
   from day one / 8 open-backlog candidates" conflated two lanes. The DRIFT lane
   (scan_drift, Option 3) IS trustworthy from day one — it emits 0 with no false
   positives. The harvest-BACKLOG candidates are a human-triage list filtered by
   two PRECISE guards (proposes-an-existing-skill; superseded-by-a-clean-harvest) —
   NOT a guaranteed-all-open set: rule-coverage and session-hardening are
   deliberately NOT guards (too fragile to automate safely), so a few candidates
   (ship — addressed S11; resume-state — enacted as FR-002) bubble for a human to
   discard. The claim, not the behavior, was wrong. Relatedly, the dashboard's
   `enacted` lane counts the rules.md digest (minted from DECISIONS by
   `regen_rules.py`, outside the draft→review pipeline); the loop's OWN enacted
   count is 0 until a draft is promoted and enacted.

**Also fixed:** `proposes_existing_skill` now matches only the FIRST named token
after "new skill" (the one being proposed), so a genuinely-new-skill finding that
merely quotes an existing skill elsewhere still bubbles. And the state file lagged
its own run log again (`s26_light_up_self_healing` logged but not in
`completed_tasks` — the very FR-002/FR-007 lag); written forward here.

**Why:** the north star is HONEST self-healing. A guard that drops an open finding
on a false basis, or a record that claims more than the code delivers, is exactly
the discipline drift this loop exists to catch — so the audit's findings are
first-class corrections, not nitpicks.

**Alternatives considered:** implement rule-coverage + session-hardening guards to
make the "all open" claim literally true (rejected: those mappings are fragile and
risk dropping real findings — the worse failure; a slightly over-inclusive,
human-triaged draft lane is safer than a falsely-pure one).

**Reversibility:** high — guard logic + records only; the 11 drafts are status=draft
and discardable via review; nothing auto-enacted.

**Supersedes:** none — corrects the 2026-06-28 drift-semantics entry's over-claim
and extends FR-002 / FR-007 (state write-forward).

## 2026-08-18 — Make the self-healing cockpit truthful and Twin-attributable

**Decision:** Treat the brain as an evidence-backed review and learning surface,
not proof that the framework healed itself. Derrick and Oracle are closed,
first-class review actors whose identity is explicitly `ui-asserted` and not
cryptographically authenticated. Proposal `accepted`, exact patch `enacted`, and
later outcome `verified` are separate lifecycle states. Every new accepting
decision stores its exact accepted body, basis, closed actor, and body digest in
the canonical proposal ledger; ignored cards and model synthesis are only
non-authoritative context. Proposal writers share a bounded advisory file lock.
Automatic draft graduation remains physically closed.

The dashboard now separates framework actions, view-only `a_bgt_rsi`
acknowledgements/history, and held backlog. Its operations band exposes bounded
source freshness, watcher/process uncertainty, projection age, cursor lag,
schema warnings, exact lifecycle counts, and tracked repository state without
service controls. Dashboard, Map, and Review must remain usable at desktop and
narrow widths, and the generated projection verifier treats the attention
partition as a frozen schema contract.

**Alternatives:** (a) keep `accepted == healed` and infer enactment from commit
messages — rejected because mention is not a path-bound patch and acceptance is
not behavioral evidence; (b) let arbitrary actor strings or `human:ui` stand for
authorship — rejected because it erases contributor identity and inflates
authentication; (c) let a passing adversarial model auto-graduate drafts —
rejected because the model is advisory, not an attributable verdict authority;
(d) turn the brain into a runtime controller — rejected because it would breach
the framework/apparatus boundary.

**Rationale:** The prior interface could self-confirm improvement while no exact
proposal-to-patch-to-test-to-later-lift chain existed. At the reviewed checkpoint
(`9783bba..fd6049e`), 147 tests pass, the generated view verifier passes 47/47,
and browser checks for Dashboard/Map/Review pass at 1440px and 390px with no
console errors or horizontal overflow. The deliberately stricter health check
reports 12 accepted proposals, 0 exact enactments, and 0 verified outcomes, so
its kill switch correctly remains triggered. That uncomfortable result is the
truth the framework must learn from.

**Reversibility:** medium — the UI/projection and read-only observations are easy
to revert; new v2 accepted-decision rows are append-only and should be superseded,
never rewritten. No live service was restarted and no `a_bgt_rsi` file was edited.

**Supersedes:** corrects the implementation semantics implied by the 2026-06-28
self-healing light-up entries; it preserves their honest-loop goal and closes the
remaining accepted/enacted conflation.
