---
name: experiment
layer: B
runtime-safe: false
description: Log a research experiment run so it is traceable and comparable. Use when starting or finishing a training run, evaluation, or ablation — captures config, seed, data version, code commit, metrics, and artifact location into the experiment ledger.
---

# experiment

Make every run traceable. An unlogged run is a result you cannot trust, compare,
or reproduce later. This skill writes one entry per run to
`memory/experiments.md`.

## When to use

Before kicking off a run (log the intent + inputs) and after it finishes (log
the outputs). Pairs with [[plan-research]] upstream and [[repro-check]] for
verification.

## What to capture

Every entry records, at minimum:

- **Run ID** — Unique and sortable (e.g. date + short slug).
- **Date**.
- **Goal** — One line; link to the plan or hypothesis.
- **Code commit** — The exact revision the run used. Refuse to log a run made
  from a dirty working tree without noting it.
- **Config** — Key hyperparameters / the config file path or hash.
- **Seed(s)**.
- **Data version** — Dataset identifier, split, and version/hash.
- **Environment** — Hardware and any environment hash, if it matters.
- **Metrics** — Primary and guardrail metrics, with values.
- **Artifacts** — Where checkpoints / logs / outputs live.
- **Verdict** — Against the decision rule from the plan: success / fail /
  inconclusive, plus a one-line interpretation.

## Procedure

1. Append a new entry to `memory/experiments.md` using the template at the top
   of that file. Newest entries go at the top.
2. On completion, fill in metrics, artifacts, and verdict — do not leave a run
   half-logged.
3. If the verdict resolves a planned decision, also append to
   `memory/DECISIONS.md`.

## Running a sequence unattended

This skill logs *one* experiment. To run a whole sequence autonomously — each
iteration proposing a change, testing it, and keeping or reverting it under a
fixed budget — use [[auto-experiment]], which drives the loop and calls back
into this skill to log each run.

## Rule

If a run cannot be described well enough to reproduce from its entry, it is not
finished — fix the entry, not just the model.
