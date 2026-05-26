---
name: brain-recall
layer: B
runtime-safe: false
pack: brain
description: Query the brain for top-N relevant entries to ground a task in prior corrections, anomalies, and decisions. Use at task start when corrections/lineage matter — bounded by recency × scope × token cap. Read-only. Dev-time only; never inherited into an apparatus-runtime skill set.
---

# brain-recall

Ground a task in what the brain already knows — without inhaling the whole
brain. The point is *bounded* recall: surface the few most-relevant pages so
the agent can self-correct against prior decisions and anomalies, then stop.
Unbounded recall would burn the context budget exactly when the agent is
about to need it.

The brain's source of truth is the JSONL ledgers and `DECISIONS.md`; this
skill *reads* them and returns short refs (slugs + one-line summaries),
never pasted bodies. The agent then **reads the page itself** when it
decides one ref is relevant.

## When to use

- **At task start**, when the task touches a topic where prior corrections
  or anomalies might apply (e.g. a validation, an experiment, a planning
  step, a publication-disposition).
- **Before [[propose]]**, to check whether the change is already covered
  by an active rule.
- **Before [[review-proposal]]**, after re-running `scripts/regen_rules.py`,
  to see neighbours of the proposal target.
- *Not* in the middle of a task as a generic search tool — that is what
  reading specific pages is for.

## Boundary — read this twice

`brain-recall` is **Layer B, dev-time only**. It must never be present in
an apparatus-runtime skill discovery path (Pi / OpenClaw / NemoClaw on the
deployed apparatus). The reason is the [[BOUNDARY]] firewall: the
apparatus emits *into* the brain via ingest scripts; it must not *read
from* a developer-curated corpus about itself at runtime. That is a
self-reference loop with no external grounding.

Verification — `install.sh --verify-firewall` and the verification
command in `BOUNDARY.md`.

## Procedure

1. **Form the query.** A query has at most three components, all optional:
   - `scope` — the skill or topic the task touches (e.g. `validate`,
     `experiment`, `day7`)
   - `tags` — keywords from the task's intent (e.g. `tool_call`, `prior`)
   - `target` — a brain page slug the task is operating *on* (e.g.
     `anomaly-tool-call-100pct`)
2. **Set bounds** (defaults shown):
   - `limit` = 5 (max refs returned)
   - `token_cap` = 800 (max characters in the rendered summary)
   - `correction_window_days` = 90 (older corrections flagged "review me")
3. **Filter candidates.** From the brain index (`memory/brain/view/index.json`
   plus `proposals.jsonl`):
   - **Always include** active corrections in scope, where "active" means
     not superseded AND `last_reviewed` within `correction_window_days`.
   - **Then include** other entities matching `scope` / `tags` / `target`
     by direct edge or shared tag.
   - **Exclude** apparatus_event entries by default (too many; usually
     noise). Opt-in via `include_apparatus_events: true`.
4. **Rank** by a simple composite: `(recency_weight × 0.5) +
   (target_proximity × 0.3) + (tag_overlap × 0.2)`, with edge-distance to
   the target as a tiebreaker.
5. **Return refs only.** One line per ref:
   `<slug> [<type>, <date>] — <title>`.
   Optionally a 1-2 sentence summary if it fits the token cap.
6. **The agent reads the page** only if a ref looks relevant. Recall does
   not inline page bodies; that is the agent's deliberate next step.

## Output shape

A briefing block at the top of the agent's working context:

```
## brain-recall (scope=validate, tags=tool_call,prior)
- dec-fw-2026-05-24-treat-100-metrics-in-small-n [correction, 2026-05-24]
    — Treat 100% metrics in small-N tests as suspicious-clean
- anomaly-tool-call-100pct [anomaly, 2026-05-20]
    — Tool-call invocation at 100% likely reflects directive prompt
- experiment-day4-tool-call-rate [experiment, 2026-05-20]
    — Day 4 end-to-end tool-call invocation rate
```

## Rules

- **Read-only.** This skill never writes. Reflections go to [[narrate]];
  proposals go to [[propose]]; rule changes go to [[decision-log]].
- **Bounded.** Every invocation declares a `limit` and a `token_cap`.
  An unbounded recall is a misuse — split the query.
- **Refs, not content.** Surface what to look at, not the looking itself.
  The agent fetches what it needs.
- **Stale corrections are flagged, not silenced.** A correction older than
  `correction_window_days` appears with a `[stale — re-review?]` tag, not
  hidden. Hiding stale rules is how stale rules get re-applied.
- **Firewalled.** Dev-time only. Never inherited into apparatus-runtime
  skill discovery (`install.sh --global-pi` excludes this skill by name).

## Pairing

[[resume-state]] and [[context-restore]] surface the *most-recent
corrections* by default in the session briefing — that is the floor.
`brain-recall` is the *task-scoped* tier above it, invoked when the
generic recent-corrections list is not enough.
