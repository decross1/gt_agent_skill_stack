# Synchronized Spatial Inspection & Mathematical Diagrams (`design/references/spatial-and-diagrams.md`)

## When to use
Use when designing or reviewing views that synchronize temporal playback across spatial/multimodal trajectories (Rerun pattern) or render formal mathematical/system invariants where geometric relationships must preserve declarative constraints (Penrose pattern).

## Data contract
```json
{
  "timeline_ticks": [0, 1, 2, 3],
  "spatial_frames": [
    {"tick": 0, "entities": [{"id": "ag-1", "x": 12.0, "y": 34.0, "state": "searching"}]}
  ],
  "declarative_diagram": {
    "domain_statements": ["Set A", "Set B", "Subset(A, B)"],
    "constraints": ["contains(circle(B), circle(A))", "disjoint(label(A), boundary(A))"]
  }
}
```

## Canonical views
1. **Rerun Synchronized Time-Scrubber & Multimodal Split View (`What happened in the simulation at tick T?`):**
   - **Question answered:** How do spatial entity positions, scalar metric trajectories, and structured event logs align at exact timestamp or step `T`?
   - **Visual encoding:** Shared bottom or top **Time Scrubber Bar** with play/step controls (`◄`, `►`, tick slider) that drives a shared cursor across (a) 2D spatial viewport, (b) time-series metric chart (vertical cursor line at `T`), and (c) event log table (auto-highlighted at `T`).
2. **Penrose Declarative Constraint Diagram (`What formal relationship holds between these mathematical/system objects?`):**
   - **Question answered:** Does the visual geometry faithfully reflect the formal invariant (e.g., `runtime-safe ⊂ core`, `valid_from <= valid_to`, scope-narrowing monotonicity `S_{t+1} ⊆ S_t`)?
   - **Visual encoding:** Inline SVG diagram paired side-by-side (or in an expandable `<details>` block) with the exact declarative domain statements and constraints that generated it so the diagram can be audited and regenerated.

## Interactions
- Scrubbing or stepping time `T` updates all linked panels synchronously in `<16ms` without layout shift.
- Hovering a formal statement in the Penrose specification highlights the corresponding geometric primitive in the SVG diagram.

## Anti-patterns
- **Don't** draw hand-wavy architectural boxes whose containment contradicts the actual system boundary (e.g., showing `brain` inside `runtime-safe`); **do** verify geometric containment against formal invariants (`BOUNDARY.md`).
- **Don't** build separate unlinked time sliders for each chart on a page; **do** bind all temporal views on a screen to one shared time cursor.

## Deterministic checks
- Every spatial/diagram SVG includes `aria-label` or `<title>` and co-located constraint/invariant text.
- Time-series and spatial panels on the same screen share a single time-selection state control.

## Sources
- Rerun (`github.com/rerun-io/rerun`, reviewed `2026-10-27`) — synchronized multimodal time scrubbing
- Penrose (Ye et al., SIGGRAPH 2020, `github.com/penrose/penrose`) — declarative mathematical diagramming
