---
name: narrate
layer: B
runtime-safe: false
pack: brain
description: Append a human-readable reflection after a task — intent, what was done, observed deltas, what to do differently, corrections honored. Use after any non-trivial task that [[run-log]] also records — captures the *why* and the lessons that the run log's structured fields cannot.
---

# narrate

Make the *reasoning* behind a task durable. `run-log` records what happened in
structured form; `narrate` records the agent's intent, the deltas it noticed,
the lessons it would carry forward, and the corrections it referenced — in
prose, indexed by the same `task_id`. The two are paired, not duplicated:
run-log is evidence, narrate is the lab-notebook entry beside it.

The point is twofold: a human reader can scan a day and understand *what the
agents were thinking*, and the agents themselves can — via [[brain-recall]]
(Phase B3) — read recent narratives to ground future work. Self-correction is
not the goal of writing; it is a byproduct of writing honestly.

## When to use

After any task whose `run-log` entry would not, by itself, let a reader
understand the *intent and lessons*. That is most non-trivial tasks. Skip
narrate only when the work is purely mechanical (e.g. running a known-good
script with a clearly logged outcome) and the run-log entry already tells the
full story.

Pairs with [[run-log]] (same `task_id`), [[decision-log]] (if the task
yielded a durable decision or a `correction:`), and [[experiment]] (if the
task was a run).

## Entry shape

Append one JSON object per line (JSONL) to `memory/brain/narratives.jsonl`.
Use the project's own schema if it defines one; otherwise this default:

```json
{
  "timestamp": "<ISO 8601>",
  "task_id": "<same identifier as the paired run-log entry>",
  "agent_id": "<who wrote this — e.g. claude-code-main, builder-subagent, apparatus_event>",
  "type": "reflection | apparatus_event",
  "intent": "<what the agent was trying to accomplish>",
  "did": "<what the agent actually did, in prose>",
  "observed": "<what was observed, especially deltas from intent>",
  "would_do_differently": "<lessons; what next time looks like>",
  "corrections_honored": ["<D-NNN or correction-slug>", "..."],
  "references": ["<other task_id, D-NNN, or brain page slug>"]
}
```

Fields are not optional placeholders. If `would_do_differently` is genuinely
empty (the task ran exactly as intended), write `"none — would do the same"`
— do not omit the field. Empty fields hide thought; explicit absence
documents it.

For ingest-projected entries (`type: apparatus_event`), `agent_id` is the
apparatus role that emitted the source event (e.g. `orchestrator_dispatcher`,
`vllm_worker`); `intent` / `did` / `observed` are derived deterministically
from the source JSONL, not synthesized.

## Declared edges

When the task connects to other brain entities — a hypothesis it tested, an
anomaly it produced, a correction it honored, a prior reflection it builds
on — declare those connections as **typed edges** appended to
`memory/brain/edges.jsonl` in the same step. Edges are the brain's wiring;
they make lineage walkable in the graph view (`memory/brain/view/graph.html`)
without inferring links from prose.

Append one JSON object per edge:

```json
{
  "timestamp": "<ISO 8601>",
  "src": "<slug of the source entity>",
  "src_type": "reflection | apparatus_event | experiment | decision | anomaly | hypothesis | correction",
  "type": "derived_from | produced | linked_to | falsified_by | supersedes | references",
  "dst": "<slug of the target entity>",
  "dst_type": "<same enum>",
  "source_event": "<task_id or narrative-task_id that authored this edge>",
  "agent_id": "<who declared it>"
}
```

Edges are **declared explicitly** — never inferred by LLM from narrative
prose. A typo in a slug is a dangling edge; the graph renderer flags it.
The six edge types are the starter set; a project may extend.

## Procedure

1. **At task end**, draft the five prose fields against the task as it
   actually unfolded — not as it was planned. The entry is *observed*, not
   *intended* (cf. [[run-log]]).
2. **Cite, do not relocate.** If a correction or decision was honored,
   reference it by ID (`D-NNN`) — do not paste the correction's text into the
   narrative. Authority lives in `memory/DECISIONS.md`; the narrative cites it.
3. **Append** to `memory/brain/narratives.jsonl`. Never edit a past entry; a
   later realization is a new entry that references the prior one.
4. **Same `task_id` as the run-log entry**, so the renderer can join them.
5. **Independent of `run-log`.** Whether the run-log says passed / failed /
   partial_pass / halted, the narrative still gets written if the task
   produced any reasoning worth keeping. A `halted` task's narrative is often
   the most valuable one.

## Rules

- **Append-only.** Narratives are the source of truth for reflection. A
  correction is a new entry that supersedes the prior, not an edit.
- **Honest, not flattering.** A narrative that says "I did X because Y" when
  the agent actually did X by accident is worse than no narrative. Future
  agents will read these to ground themselves.
- **Reference, do not duplicate.** Decisions live in `DECISIONS.md`. Run-log
  evidence lives in the run log. Apparatus metrics live in their JSONL. The
  narrative is the prose layer above them; it points to them.
- **Bounded length.** A narrative entry is for one task. If it grows into a
  decision, lift the decision part out to [[decision-log]] and reference it
  by ID.

## Pairing

The structured execution trace is [[run-log]]; durable decisions are
[[decision-log]]; experiment runs are [[experiment]]. The renderer
`scripts/render_brain.py` joins all four (by `task_id` and date) into a
per-day human-readable view at `memory/brain/view/<YYYY-MM-DD>.md`. The
deterministic apparatus projection `scripts/ingest_apparatus.py` writes
`apparatus_event` narratives so the apparatus runtime shows up in the same
view alongside dev-time work, without the apparatus depending on this skill.
