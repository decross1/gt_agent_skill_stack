# Skill packs

Skills group into **packs** — opt-in collections that share a domain. A
consumer picks the packs it needs; the framework's `core` pack is always
included.

The pack field is **per-skill frontmatter** in each `SKILL.md`. This file is
a derived view of those assignments, kept in sync by hand for now (a future
session may automate regeneration). Authoritative source: the frontmatter.

## Pack matrix

| Pack | Always installed? | Layer mix | Count | What it covers |
|---|---|---|---|---|
| `core`     | yes — every consumer | A + Layer-B discipline extensions | 7 | Execution-discipline primitives. The runtime-safe core (6) plus general discipline extensions (slip-ladder). |
| `meta`     | yes — every consumer | C                                  | 5 | Framework-internal infrastructure: session memory, decision log, harvest loop, orchestration. |
| `research` | opt-in              | B                                  | 8 | The research lifecycle: plan → run → reproduce → investigate → review → ship. |
| `brain`    | opt-in              | B                                  | 4 | Observation, reflection, and proposal-review against a typed brain graph. |

Total: 24 skills today.

## Pack contents

### `core` (always installed)

The 6 runtime-safe skills (Layer A) plus `slip-ladder` (Layer B but general
discipline, not a vertical). These are the framework's baseline — any
consumer that adopts the framework adopts these.

- `fallback` (A) — switch to a declared alternative when the primary fails.
- `gate-check` (A) — halt at human gates / irreversible actions.
- `resume-state` (A) — start-of-session: read plan + state, find resume point.
- `run-log` (A) — append-only execution trace.
- `validate` (A) — independent per-check pass/fail evaluation.
- `spawn-contract` (A) — autonomous child spawn under explicit contract.
- `slip-ladder` (B) — bounded deadline-extension protocol.

### `meta` (always installed)

Framework-internal infrastructure. Dev-time only.

- `context-restore` — rebuild context at session start.
- `context-save` — write a handoff snapshot at session end.
- `decision-log` — append-only durable-decision ledger.
- `harvest` — read a consumer's trace to score the framework's own skills.
- `orchestrate` — dev-time multi-role delegation (with human in loop).

### `research` (opt-in vertical)

The research lifecycle. Use this pack when the project is a research
program (experiments, baselines, results, peer-style review).

- `plan-research` — design a falsifiable plan (hypothesis, baseline, metric).
- `experiment` — log a single run to the experiment ledger.
- `auto-experiment` — run an unattended experiment sequence under a budget.
- `repro-check` — verify a result is reproducible before trusting it.
- `investigate` — evidence-based debugging via a hypothesis tree.
- `code-review` — pre-merge review (research-specific risks called out).
- `health` — periodic project-health snapshot.
- `ship` — last-mile: test → commit → integrate → record decision.

### `brain` (opt-in vertical)

The observation + reflection + proposal-review substrate. Use this pack when
the project benefits from a typed knowledge graph over its own activity.

- `narrate` — end-of-task reflection writeback to the brain.
- `brain-recall` — bounded query into the brain for grounding.
- `propose` — file a proposal to change a brain page, rule, or skill.
- `review-proposal` — evaluate proposals against active rules.

## How to install (today)

The pack field is read but **not yet a filter** in `install.sh`. Today every
target installs all skills that satisfy its `filter` (e.g. `runtime-safe`
for the Pi target). Pack-aware install is on the v2 roadmap; the
frontmatter declaration ships now so consumers can choose by *reading the
field* even before the install script enforces it.

See `install.sh --list-packs` for the current pack inventory.

## How to add a new vertical pack

Concrete steps:

1. **Decide the pack name.** Short, lowercase, vertical-domain — e.g.
   `product`, `data-pipeline`, `ml-ops`, `security`.

2. **Identify the skills.** What does this vertical need that's *not* in
   `core` or `meta`? List each as a one-line purpose. If a skill belongs in
   `core` or already exists in another pack, don't duplicate it — the
   consumer's install will pull `core` automatically.

3. **Author each new skill's `SKILL.md`** under `.agents/skills/<name>/`
   following the standard frontmatter:
   ```yaml
   ---
   name: <skill-name>
   layer: B            # most vertical skills are Layer B; Layer A only if
                       # the skill satisfies the runtime-safe contract
   runtime-safe: false # set true only after auditing BOUNDARY.md:50-65
   pack: <your-pack>
   description: <one sentence; what the skill does + when to use>
   ---
   ```
   Then the body, matching the style of existing skills: a short intro, a
   "When to use" section, a "Procedure", and "Rules".

4. **Add a row to the Pack matrix above** and a section below it listing
   the new pack's skills.

5. **No `install.sh` change needed today** — the pack field is read, not
   filtered. When pack-aware install lands, you may then declare which
   targets default to which packs.

6. **Run `install.sh --list-packs` to verify** the framework sees the new
   pack (it walks the `pack:` frontmatter field). If the new pack
   appears with the expected count, you're done.

## Pack-vs-layer cheat sheet

The two fields are **orthogonal**:

- **Layer** (A/B/C) — discipline tier. A is runtime-safe core; B is
  dev-time vertical content; C is framework infra. Determined by
  `install.sh`'s `runtime-safe` filter.
- **Pack** (core/meta/research/brain/…) — which vertical or baseline the
  skill belongs to. Determined by *user choice* (future install filter).

A Layer-A skill is always `pack: core`. A Layer-B skill is usually a
vertical pack, but may be `core` if it's general discipline (see
`slip-ladder`). A Layer-C skill is typically `pack: meta`.
