# Context Graphs & 2D Spatial Canvases (`design/references/graphs.md`)

## When to use
Use when designing or reviewing 2D spatial canvases (`oracle_system` Portal `:8790` Essence Atlas & Obsidian Canvas viewer, Brain `:5180` `graph.html` cluster map), decision provenance graphs (`DECISIONS.md` `D-NNN` traces), or entity/hypothesis neighborhood explorers.

## Data contract
1. **Spatial Canvas Schema (JSON Canvas 1.0 + Epistemic Extensions):**
```json
{
  "nodes": [
    {
      "id": "domain:agent_architecture",
      "type": "text",
      "x": 120,
      "y": 80,
      "width": 260,
      "height": 110,
      "text": "Autonomous Agent Harnesses",
      "category": "neighborhood",
      "epistemic_label": "observed",
      "weight": 14
    }
  ],
  "edges": [
    {
      "id": "e-1",
      "fromNode": "note:evt_sha256_7aeed2af",
      "toNode": "domain:agent_architecture",
      "label": "resonates_with",
      "edge_type": "semantic",
      "epistemic_label": "oracle_taste"
    }
  ]
}
```
2. **Decision Trace Schema (Foundation Capital Context Graph Model):**
   `decision_id (D-NNN) → {inputs, policy_version, precedent_links[], approver, outcome, kill_reason}`.

## Canonical views
1. **2D Spatial Canvas with Minimap & Neighborhood Sidebar (`How do domains, notes, and systems connect spatially?`):**
   - **Question answered:** Which research domains cluster together, where do owner notes and lateral curiosity bridges (`oracle_taste`) land, and which nodes have the highest activity?
   - **Visual encoding:**
     - **Scale rule:** Below `2,000` nodes, use **deterministic precomputed coordinates rendered in inline SVG or 2D HTML5 Canvas** with pan/zoom and crisp text labels. Never import heavy WebGL engines (`Sigma.js` / `cosmos.gl`) for `<2,000` nodes.
     - **Node encoding:** Position `(x, y)` = stable cluster layout; border color/style = category & `epistemic_label` (solid = `observed`, dashed = `inferred`/`oracle_taste`); badge = degree/event count.
     - **Edge encoding:** Directed bezier or orthogonal path with explicit arrowhead (`marker-end`), stroke style by `edge_type` (`causal` = solid, `temporal` = dotted, `semantic`/`bridge` = dashed accent).
     - **Required companion panels:** A graph overview alone is never a complete workflow. Pair the canvas with:
       1. Left/Top **Filter & Search Bar** (search by label, filter by category/edge type, `Fit to Screen` / `Reset Zoom` buttons).
       2. Right **Selected Node Inspector** showing incoming/outgoing edges, verbatim source excerpt, timestamps, and direct links.
2. **Decision Precedent Table + Focused Ego-Graph (`Why was D-NNN decided, and what precedent does it cite?`):**
   - **Question answered:** Which prior decisions (`D-NNN`), harvest findings (`H-NNN`), or kill codes governed a choice?
   - **Visual encoding:** Default to a **filterable, high-density Decision Trace Table** first; render a 1-hop or 2-hop ego-graph in the detail pane when a row is selected.

## Interactions
- **Pan & Zoom:** Drag background to pan, wheel/buttons to zoom (`0.25x`–`2.5x`), `Fit View` button to center all visible nodes automatically on first render.
- **1-Hop Ego Highlight:** Clicking a node highlights its immediate neighbors and connected edges while dimming unrelated nodes (`opacity: 0.22`), and opens the right-hand Inspector.
- **Keyboard accessible:** Node list in sidebar allows full keyboard traversal of the graph even without mouse dragging.

## Anti-patterns
- **Don't** render a canvas where nodes spawn off-screen or at `(0,0)` overlapping each other; **do** compute bounding boxes and auto-fit the viewport on load.
- **Don't** draw unlabeled edges without a legend; **do** include an explicit visual legend mapping stroke style and color to edge semantics (`observed`, `inferred`, `oracle_taste`).
- **Don't** use a 3D or unstabilized force layout that jitters on every poll; **do** keep node positions deterministic across refreshes.

## Deterministic checks
- Every `<svg>` or `<canvas>` spatial view is paired with a keyboard-accessible node list or inspector panel and a `Fit` / `Reset` control.
- Node coordinates are finite numbers with zero full-node overlaps in default layout.
- Legend explaining node/edge types is present in the DOM.

## Sources
- Obsidian JSON Canvas 1.0 Spec (`jsoncanvas.org`, reviewed `2026-10-27`)
- React Flow / `xyflow` (`github.com/xyflow/xyflow`) — viewport controls, minimap & node selection patterns
- UW Mosaic (`github.com/uwdata/mosaic`) — linked cross-filtering between table and canvas
- Foundation Capital, *AI Context Graphs* (Gupta & Garg, Dec 2025) — decision trace data model
