# Bi-Temporal Context & Agent Memory (`design/references/memory.md`)

## When to use
Use when designing or reviewing views of agent memory, context-window token allocation, belief evolution, source lineage, or historical supersession (`oracle_system` Memory Cockpit `:8765`, Oracle Portal `:8790` Essence/Today Delta, Brain `:5180` recall & narratives). Fixture: `design/evals/memory_fixture.json`.

## Data contract
Combines **Letta ADE** context-window budgets, **Zep/Graphiti** 4-timestamp bitemporal edges, and **MAGMA** 4-layer multigraph edges (`Semantic`, `Temporal`, `Causal`, `Entity`):
```json
{
  "context_budget": {
    "max_tokens": 131072,
    "sections": [
      {"name": "system_instructions", "tokens": 4200},
      {"name": "tool_schemas", "tokens": 6800},
      {"name": "core_memory", "tokens": 8500},
      {"name": "retrieved_episodes", "tokens": 19200},
      {"name": "event_queue", "tokens": 12400}
    ],
    "evicted_tokens": 3100
  },
  "bitemporal_claims": [
    {
      "claim_id": "clm-204",
      "subject": "portal_drift:lab_dashboard_5173",
      "predicate": "release_source",
      "object": "source/RELEASE.json",
      "edge_layer": "Causal",
      "epistemic_label": "observed",
      "valid_from": "2026-10-27T02:11:00Z",
      "valid_to": null,
      "created_at": "2026-10-27T02:11:05Z",
      "expired_at": null,
      "superseded_by": null,
      "source_episode": "evt_sha256_7aeed2af"
    }
  ]
}
```

## Canonical views
1. **Letta ADE Context-Window Budget Bar (`How is the agent's context window allocated?`):**
   - **Question answered:** Which memory section dominates the context window, how much headroom remains, and did eviction/compaction occur?
   - **Visual encoding:** Single horizontal stacked bar (`0` → `max_tokens`) segmented by section (`system`, `tools`, `core_memory`, `episodes`, `queue`, `headroom`) with an explicit overflow/eviction callout badge when `evicted_tokens > 0`.
2. **Zep/Graphiti Bi-Temporal Belief Inspector (`What does the agent believe now vs. then, and what superseded it?`):**
   - **Question answered:** Which claim is currently valid (`valid_to == null` and `expired_at == null`), which prior claim was superseded, when was it ingested (`created_at`), and are there unresolved contradictions?
   - **Visual encoding:**
     - **Active Claims Table / Timeline:** Solid border (`--ok` / `--epistemic-observed`), showing `valid_from` → `Present` and clickable `source_episode`.
     - **Superseded / Historical Claims:** Muted row with strikethrough or `Superseded by <claim_id>` link and explicit `[valid_from → valid_to]` interval bar.
     - **Contradiction / Missing Provenance Alert:** Claims with conflicting active objects or `source_episode == null` render a `--warn` (`⚠ Unresolved conflict` or `⚠ Missing provenance`) badge.
3. **MAGMA 4-Layer Causal & Temporal Linearization View (`Why did this state transition happen?`):**
   - **Question answered:** What sequence of causes (`E_causal`) and events (`E_temporal`) led to the current belief?
   - **Visual encoding:** Directed topological chain sorted via `design/scripts/linearize_context.py` so causes strictly precede effects (`cause → effect`), with layer filter pills (`All`, `Causal`, `Temporal`, `Semantic`, `Entity`).

## Interactions
- **Time-Scrubber / As-Of Query:** Filtering by timestamp `t` highlights claims where `valid_from <= t < (valid_to or ∞)` and `created_at <= t < (expired_at or ∞)`.
- **Intent Routing Toggle:** Switch between `WHY (Causal topological order)` and `WHEN (Chronological timeline)`.
- **Supersession Drill-Down:** Clicking `Superseded by` or `Prior version` steps through the belief lineage chain.

## Anti-patterns
- **Don't** render memory as a static, undated node-link hairball; **do** include a time axis and explicit `active` vs. `superseded` vs. `conflicting` states.
- **Don't** silently hide superseded beliefs; **do** keep historical beliefs inspectable via a `Show Superseded (N)` toggle so belief drift can be audited.
- **Don't** mix causal edges with generic semantic similarity edges without visual distinction; **do** encode `Causal` edges with directional arrows (`→`) and solid strokes, and `Semantic` resonance edges (`oracle_taste`) with dashed accent strokes.

## Deterministic checks
- Bi-temporal views distinguish active claims from superseded claims in DOM attributes (`data-state="active|superseded|conflict"`).
- Every claim displays or links to its `source_episode` (or flags `missing-provenance` explicitly).
- Causal chains preserve topological order (`design/scripts/linearize_context.py --check`).

## Sources
- Zep / Graphiti (Rasmussen et al., 2025, `arXiv:2501.13956`, `github.com/getzep/graphiti`)
- MAGMA: Multi-Graph based Agentic Memory Architecture (Jiang et al., ACL 2026, `arXiv:2601.03236`)
- Letta ADE Context Window Viewer (`docs.letta.com/guides/ade`, reviewed `2026-10-27`)
- EverMemOS (`arXiv:2601.02163`) — verbatim episode retention alongside semantic abstractions
