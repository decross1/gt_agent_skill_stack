# <Representation Name>

## When to use
Data shapes and user questions that route here. Link to fixture in `design/evals/`.

## Data contract
Minimal normalized JSON/record schema the view expects. Adapter notes for repository sources (`state/events.jsonl`, `spawn.jsonl`, `feedback.jsonl`, `DECISIONS.md`).

## Canonical views
1–4 views, each specifying:
- **Question answered:** ...
- **Visual encoding:** mark, position, color token, size, text/badge treatment
- **Default sort & grouping:** ...

## Interactions
Interactions that survive zero-dep inline JS or lightweight state: selection, cross-filtering, sort, time-window scrub, progressive detail drawer.

## Anti-patterns
Specific failure modes seen in coding-agent output, each written as:
- **Don't** X; **do** Y.

## Deterministic checks
Script-checkable assertions enforced by `design/scripts/qa_gate.py`.

## Sources
Upstream repositories and papers with reviewed date (`2026-10-27`).
