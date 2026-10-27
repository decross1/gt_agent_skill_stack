---
name: lab-ui-plan
description: Produce a Munzner Nested Model screen brief and Component & State Topology Graph before writing or overhauling any research-lab UI. Use at the start of any UI task on Oracle Portal (:8790), Cockpit (:8765), Nara Lab (:5173), or Brain (:5180).
layer: B
runtime-safe: false
pack: design
---

# `lab-ui-plan` — Munzner Nested Model Screen Brief & Spatial Topology Planning

## When to Use
Invoke `lab-ui-plan` **before** editing HTML, CSS, or frontend JS/TS on any research-lab surface (`:8790`, `:8765`, `:5173`, `:5180`). Planning prevents the #1 agent UI failure mode: dumping raw backend JSON objects into `<dl>` lists without deciding what operator decision each screen supports.

## Workflow

### Step 1 — Read Product & System Context
1. Read `design/product.md` (surface roles across `:8790`, `:8765`, `:5173`, `:5180` and governance red gates).
2. Read `design/system.md` (`SHARED TOKENS v1`, typography scale, dark-first luminance hierarchy, epistemic badge grammar).
3. If inspecting an existing HTML/DOM tree, linearize its structure first:
   ```bash
   python3 design/scripts/linearize_context.py <path-to-html>
   ```

### Step 2 — Write the 4-Level Munzner Screen Brief
For each workspace/tab being created or overhauled, specify:
1. **Domain Situation (Who & Why)**: Which operator loop does this screen serve (e.g., 30-second morning continuity check, lateral-bridge synthesis inspection, paper-only risk gate audit)?
2. **Data & Task Abstraction (What)**: Exact server endpoint(s), payload fields, and the distinction between `0`, `unmeasured`, `stale`, `failed`, and `observed`.
3. **Visual Encoding & Interaction Idiom (How)**: Route each data shape via `[[agent-viz]]` (`design/reference-index.md`) to a KPI strip, aligned `tabular-nums` table, bullet bar, 7-stage pipeline stepper, or interactive SVG canvas.
4. **Algorithmic / Contract Constraints**: Existing unit/Node-VM test contracts (e.g. `tests/test_portal_view.py`, `tests/test_portal_ui.py`), response-time budgets, and offline/Tailscale constraints.

### Step 3 — Emit the Component & State Topology Graph
Sketch the landmarks, tab panels, and data-binding targets as an explicit tree before writing code:
```text
[header#portal-topbar] ── service-strip (drift.services) + Unlock/Refresh actions
[nav.portal-tabs role=tablist] ── 6 tabs (ArrowLeft/ArrowRight/Home/End)
[main#portal-main]
 ├── #tab-command   ── .kpi-grid (6 subsystem cards) + Release Parity <table>
 ├── #tab-lab       ── Workspace links (:5173/:5180) + 5-Pipe <table> + Fleet Bus <table> + Quota Bullet Bars & <table> + Delta/Notes/Musings
 ├── #tab-atlas     ── Pan/Zoom/Fit toolbar + <svg#atlas-svg> (core L-paths, lateral Q-curves, 1-hop ego highlight) + #atlas-inspector
 ├── #tab-obsidian  ── Split sidebar (#obsidian-tree + truncation warning) + viewer (<pre> markdown or <svg> canvas)
 ├── #tab-hourglass ── Red-gate banner + 5-Band stack (Posture gauges, Promotion gates, 7-Stage stepper, Brier comparison, Audit tables)
 └── #tab-notes     ── Opt-in capture form (draft retention on error/partial) + Bitemporal Gateway Receipt
```

## Handoff
Pass the completed Screen Brief and Topology Graph to `[[agent-viz]]` and `[[lab-ui-build]]`, then verify the built artifact with `[[lab-ui-review]]`.
