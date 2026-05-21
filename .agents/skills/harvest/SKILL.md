---
name: harvest
description: Harvest feedback for the framework's own skills from a consumer project's execution trace. Use once per consumer work session — reads the consumer's run log, git history, and decision log since a stored watermark, classifies each finding against the skill it bears on, and appends to the feedback ledger. Read-only on the consumer.
---

# harvest

Turn a consumer project's real execution trace into evidence about the
framework's own skills. The framework is only as good as its skills are
*accurate, complete, and frictionless* against real disciplined work — `harvest`
is how that is measured rather than assumed.

This is a **dev-time, framework-internal** skill: it improves the framework
itself. It is **read-only on the consumer** — it never modifies, advises, or
instruments the project it harvests.

## When to use

Once per consumer work session, as the second step of the framework's own
session loop (after [[resume-state]]). Also for a one-time baseline harvest over
a consumer's entire history.

## Inputs

- The **consumer's execution trace** — its run log (JSONL), git history, and
  decision log. For `a_bgt_rsi`: `run_state/week1.run.jsonl`, `git log`,
  `DECISIONS.md`.
- The **watermark** — `harvest_watermark.<consumer>` in
  `run_state/framework.state.json`: how far the last harvest read
  (`run_jsonl_lines`, `last_commit`, `last_decision`).
- The **skill set under evaluation** — the framework's own `.agents/skills/`.

## Procedure

1. **Read the watermark** for this consumer from `framework.state.json`.
2. **Collect what is new** since the watermark — run-log lines beyond
   `run_jsonl_lines`, commits after `last_commit`, decisions after
   `last_decision`. If nothing is new, stop — there is nothing to harvest.
3. **For each new item, find the skill it bears on.** A logged validation bears
   on [[validate]]; a logged fallback on [[fallback]]; a state-file resume on
   [[resume-state]]; an audit or review on [[code-review]]; a logged step on
   [[run-log]]. One item may bear on more than one skill — that is more than one
   finding.
4. **Classify each finding** by the rubric below.
5. **Append one entry per finding** to `memory/feedback.jsonl` (shape below).
6. **Advance the watermark** to the end of what was read; write it back to
   `framework.state.json`. The watermark only ever moves forward.
7. **Summarize** — a short per-skill conformance tally for the session briefing.

## Classification rubric

- **`confirmed`** — the consumer's behavior matched what the skill prescribes.
  Evidence the skill is accurate; logged, not discarded — accumulated
  confirmations are how a skill earns "hardened" status.
- **`diverged`** — the consumer did the thing the skill governs, but differently
  from, or contrary to, the skill. Either the skill is wrong or the consumer is;
  the finding names which to investigate.
- **`gap`** — the consumer needed discipline that *no* skill covers. A candidate
  for a new skill or a new section.
- **`friction`** — a skill covers this, but invoking it as written would have
  been awkward, redundant, or mis-fitted to the consumer's reality. A skill-edit
  candidate.

A finding that is none of these is not a finding — do not log noise, and do not
log the same confirmation twice.

## Feedback entry shape

One JSON object per line, appended to `memory/feedback.jsonl`:

```json
{
  "harvest_id": "<harvest-run id: H + zero-padded sequence>",
  "date": "<ISO 8601>",
  "source": "<consumer name>",
  "ref": "<pointer into the consumer trace: run-log line, task_id, commit, D-NNN>",
  "skill": "<framework skill the finding bears on>",
  "class": "confirmed | diverged | gap | friction",
  "evidence": "<what was observed, concretely, quoting the trace>",
  "plan_candidate": "<backlog item this implies, or null>"
}
```

## Output

The appended `feedback.jsonl` entries, plus a briefing: per skill, the tally of
`confirmed` / `diverged` / `gap` / `friction` for this harvest, and the backlog
candidates produced. The framework's session loop feeds that into its re-sort.

## Rules

- **Read-only on the consumer.** A consumer must be safe to harvest without
  knowing it happened.
- **The watermark only moves forward.** A harvested item is never re-harvested;
  a re-run from the new watermark produces zero entries.
- **One finding, one entry.** Do not bundle; do not split a single observation.
- **Confirmations count.** A `confirmed` finding is logged with the same rigor
  as a problem — a skill is trusted because of accumulated confirmations, not
  the mere absence of complaints.
- **`harvest` observes; it does not fix.** Findings become backlog items for a
  later session. Editing a skill in the same pass that harvested it would
  collapse the evidence and the change into one unreviewable step.
