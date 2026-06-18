# Handoff — a_bgt_rsi runtime skill-signals stream

_Status: an instruction handoff for the **a_bgt_rsi owner** to start emitting a
first-class, at-runtime skill-friction stream. The **framework side is already
stubbed and tested** against `tests/fixtures/skill_signals.jsonl` —
`scripts/ingest_apparatus.py` recognizes a skill-signal by shape, projects it
into an `apparatus_event` narrative, and writes a `source="runtime"` row into
`memory/brain/drift_signals.jsonl`. Nothing is wired into the consumer yet; that
is what this handoff asks for. Apparatus owns the emit; the framework owns the
ingest._

> **RECONCILED 2026-06-18.** The a_bgt_rsi owner adversarially reviewed this
> handoff and adopted it with reconciliations (their **D-056** +
> `a_bgt_rsi/docs/skill_signals_contract.md`, which is now the **authoritative
> apparatus-side contract**). Two corrections are folded in below: **(1)** trigger
> **(a)** is reframed off the framework's run-log enum (their run-log is
> open-vocabulary by their rule 6, so a non-enum status is the NORM, not friction);
> **(2)** the firewall obligation is cited from the apparatus's **own** rules, not
> from reading this framework's `BOUNDARY.md`. Neither changes the framework ingest
> — it keys only on `signal_class` + `skill`, never on the trigger or the enum. See
> the reply `handoffs/2026-06-18-a_bgt_rsi-skill-signals-reply.md`.

- **What:** a per-event append to `a_bgt_rsi/run_state/skill_signals.jsonl` the
  moment an agent hits friction with a framework skill.
- **Owner:** the a_bgt_rsi runtime (the agents doing the project's actual work).
- **Framework basis:** drift-detection plan (`detected → candidates → open →
  decided`); this stream is the `source="runtime"` half of the **detected** lane.

## Why this exists

Today drift against the framework's skills is **reconstructed after the fact**.
The `harvest` skill reads the consumer trace once per session and classifies
findings by judgment into `feedback.jsonl`; `narrate` adds a human-readable
reflection. Both are post-hoc and lossy — by the time harvest runs, the agent
that actually felt the skill mis-fit is gone, and only what survived in the
run-log and git history can be recovered.

A skill-signal is the **at-runtime, first-class event**: the agent that hit the
friction/misuse/gap records it _at the moment it happened_, with the context only
that agent has. It does not replace harvest — it feeds it, turning a reconstruction
job into an ingest job.

## The firewall (non-negotiable)

This stream crosses the dev-time / runtime boundary. The geometry is absolute and
both sides agree on it:

- The **apparatus writes ONLY its own log** — `a_bgt_rsi/run_state/skill_signals.jsonl`.
- The **framework reads it READ-ONLY** via `scripts/ingest_apparatus.py`. The
  framework never writes back into a_bgt_rsi.
- The **apparatus must never write into, read from, or import the brain**. No
  `memory/brain/*` access, no importing framework projection code, no calling a
  framework script. The apparatus emits a plain JSONL line and keeps going; the
  framework discovers it on its own ingest pass.

The only channel between the two systems is this one append-only file, read in one
direction. **The apparatus honors this obligation by citing its _own_ rules — not
by reading this framework's `BOUNDARY.md`** (a_bgt_rsi has no `BOUNDARY.md` and its
D-032 consciously diverges from it; requiring it to read a framework doc to learn
its own obligation would itself be a soft crossing). On the apparatus side the
governing rules are **D-014 + its CLAUDE.md Dynamic-Workflow rule 3**; this
framework's `BOUNDARY.md` ("Two orchestrators, one word") states the same geometry
for the framework side only.

## Where to write

```
a_bgt_rsi/run_state/skill_signals.jsonl
```

- **Append-only.** One JSON object per line. Never edit or rewrite a prior line.
- Lives in `run_state/` alongside `run.jsonl` — it is runtime exhaust, not source.
- Compact is fine; the framework re-parses each line on ingest.

## The event schema

Emit these fields. Do **not** emit `_source` — the framework adds it on ingest.

| Field | Required | Type / values | Notes |
|---|---|---|---|
| `timestamp` | yes | ISO 8601 | when the friction occurred |
| `agent` | yes | string | the actor, e.g. `workflow:wf_xxx/<role>` |
| `skill` | yes | string | **must name a real framework skill** (e.g. `run-log`, `validate`, `fallback`) |
| `signal_class` | yes | `friction` \| `misuse` \| `gap` | the kind of event (see "When to emit") |
| `severity` | yes | `low` \| `med` \| `high` | the agent's honest read of impact |
| `evidence` | yes | string | short, concrete one-liner — what actually happened |
| `task_id` | yes | string | **share with the run-log row** for the same step |
| `invocation_ref` | no | `"<file>:L<n>"` | where in the trace, if known at emit time |
| `expected` | no | string | what the skill should have done |
| `actual` | no | string | what it did instead |
| `suggested_fix` | no | string | the agent's hint for the next human triager |

`task_id` is the join key: it ties the signal to the `run.jsonl` step so the
framework (and a later harvest) can correlate the friction with the executed work.

## When to emit

Emit **one non-blocking append at the friction moment**, then keep going.
Emitting a signal is **not a failure** and must never stop or gate the task. The
three triggers:

- **(a) friction — REFRAMED** — a framework skill's prescribed procedure genuinely
  **could not express the step**: the agent had to invent an ad-hoc action with no
  honest fit because nothing the skill offered applied. This is feedback _about the
  framework skill_, not an apparatus self-constraint. **It is NOT** "a run-log
  status outside the framework's 8-word enum" — the apparatus run-log is
  open-vocabulary by its rule 6, so a non-enum status is the expected norm, not
  friction. When in doubt, prefer (b)/(c); (a) may be dropped entirely. _(See the
  reply for which form the framework prefers.)_
- **(b) gap** — a prescribed skill step is **blocked by a missing dependency**
  (a tool, a file, a precondition the skill assumes but the apparatus lacks).
- **(c) misuse** — you **substituted your own procedure** because the skill
  mis-fit the situation; you diverged from the prescribed path.

Pick the closest `signal_class`, write a concrete `evidence` line, append, and
continue the task on whatever path you actually took.

## A worked example

```json
{"timestamp":"2026-06-18T14:22:05Z","agent":"workflow:wf_a91/builder","skill":"fallback","signal_class":"misuse","severity":"low","evidence":"used fallback to RE-RUN the same approach after a transient error; fallback is for switching to a different approach, not retrying the primary","task_id":"D-040-iter-014","invocation_ref":"week3.run.jsonl:L412","expected":"switch to an alternative approach","actual":"re-ran the primary under the fallback label","suggested_fix":"fallback: a same-approach retry is slip-ladder, not fallback"}
```

_(This example is a `(c) misuse` — chosen deliberately over the original
`status='recovered'` one, which was an enum-keyed friction case the apparatus
correctly rejected: `recovered` is a legitimate live status in its open-vocabulary
run log, not friction.)_

Tracing this row through the pipeline: the apparatus appends it to
`skill_signals.jsonl`. On its next pass, the framework's `ingest_apparatus.py`
projects it into (1) an `apparatus_event` **narrative** (so it shows up in the
brain graph) and (2) a `source="runtime"` row in
`memory/brain/drift_signals.jsonl` (the detected lane). `draft_proposals.py`
then bubbles drift-class signals into a **DRAFT proposal** for human triage —
a draft, never a live "needs review" item, so nothing auto-enacts.

Note on wording: a `signal_class` of `"misuse"` is recorded downstream as
`"diverged"` (the framework maps `misuse → diverged`), but the original word is
**preserved verbatim in the `evidence`** string, so the agent's framing is never
lost.

## What NOT to do

- **No brain access.** Do not write to, read from, or import anything under
  `memory/brain/` or any framework script. Emit the line and stop.
- **Do not block the task.** The append is fire-and-forget. If writing the
  signal fails, swallow it and continue — a lost signal is acceptable, a stalled
  task is not.
- **Do not backfill line numbers.** `invocation_ref` is optional; if you do not
  know the line at emit time, omit it. Do not pause to compute it or rewrite the
  line later (the file is append-only).
- **Do not emit `_source`** — the framework owns that field.

## Acceptance criteria

1. `a_bgt_rsi/run_state/skill_signals.jsonl` exists and grows append-only, one
   valid JSON object per line.
2. Every emitted row carries all required fields, with `skill` naming a real
   framework skill and `task_id` matching the corresponding `run.jsonl` step.
3. No row contains `_source`; no apparatus code reads/writes/imports the brain.
4. Emitting never blocks or fails a task (verified by an emit-path that catches
   and swallows its own errors).
**Framework-side acceptance (NOT part of the apparatus's set — the apparatus can't
run our ingest):** the framework ingest (`ingest_apparatus.py`) parses the live
file and projects each row into a narrative + a `drift_signals.jsonl`
`source="runtime"` row — the same path already green against
`tests/fixtures/skill_signals.jsonl`. We own this check.

## Context-injection prompt for the next a_bgt_rsi session

> **Context:** Stand up the runtime skill-signals stream (framework side is
> already stubbed + tested).
> **Instruction:** Add a single one-append helper `emit_skill_signal(...)` that
> writes one JSON object per line to `run_state/skill_signals.jsonl` with the
> schema `{timestamp, agent, skill, signal_class (friction|misuse|gap), severity
> (low|med|high), evidence, task_id, + optional invocation_ref/expected/actual/
> suggested_fix}` — and do **not** emit `_source`. Call it at the friction
> moments: (b) a skill step blocked by a missing dependency, (c) substituting your
> own procedure because the skill mis-fit, and — only if kept — (a) a framework
> skill that genuinely could not express the step (NOT merely a run-log status
> outside the framework's enum; your run-log is open-vocab by rule 6). Share
> `task_id` with the run-log row for the same step. The append must be
> non-blocking — catch and swallow any write error and continue the task, but
> never mask the mandatory run-log write and leave one logged breadcrumb on emit
> failure (rule 7). **Never touch the brain** (no reads/writes/imports of
> `memory/brain/*` or framework scripts); honor the firewall via your own rules
> (D-014 + CLAUDE.md rule 3), not by reading the framework's `BOUNDARY.md`.
