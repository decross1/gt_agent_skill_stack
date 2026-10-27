---
name: agent-viz
description: Route research-lab data shapes and operator questions to canonical visual representations (bitemporal state graphs, spatial essence atlases, quantitative risk bands, experiment Pareto/ablation tables, and multi-agent fleet topologies). Use when planning or building any chart, SVG canvas, graph, timeline, or structured data view across Oracle, Nara, or Brain UIs.
layer: B
runtime-safe: false
pack: design
---

# `agent-viz` — Question-to-Representation Routing & Domain Visualization Craft

## When to Use
Invoke `agent-viz` whenever a UI or notebook/report needs to represent structured data, multi-agent coordination, bitemporal state, spatial neighborhoods, or quantitative risk:
- **Oracle Portal (`:8790`) & Cockpit (`:8765`)**: Spatial Essence Atlas, 5-Pipe Continuity Matrix, HOURGLASS 5-Band Risk Stack, Obsidian Vault & Canvas projection, Subscription Quota & Burn envelopes.
- **Nara Research Lab (`:5173`)**: Experiment run timelines, loss/reward curves with regime bands, hyperparameter sensitivity, promotion gates.
- **Brain Knowledge Graph (`:5180`)**: Typed claim/evidence graphs, bitemporal (`valid_at` vs `recorded_at`) diff lanes.

## Step 1 — Route by Operator Question (Munzner What–Why–How)

Never pick a chart or layout before stating the **operator question** and **data shape**. Consult `design/reference-index.md` and load only the matching domain reference:

| Operator Question | Data Shape | Canonical Representation | Reference File |
|---|---|---|---|
| *Is the system healthy and aligned with git HEAD?* | 5–8 service/subsystem statuses + commit SHAs | **Topbar Service Pill Strip + KPI Metric Strip + Release Parity Table** | `design/references/agent-observability.md` |
| *Which continuity pipes or agent inboxes are blocked?* | 5 pipes × status/evidence/action; N agents × rx/tx/unacked | **5-Pipe Health Matrix Table + Fleet Bus Coordination Table** | `design/references/agent-observability.md` |
| *How close is each model lane to its reserve floor?* | Remaining %, burn %, reserve floor %, ceilings | **Bullet Bar with Reserve Floor Tick + Tabular-Nums Readout** | `design/references/quant-financial.md` |
| *How do personal notes connect to portfolio domains?* | Spatial 2D neighborhoods + core edges + lateral bridges | **2D Spatial Essence Atlas (SVG pan/zoom/fit + 1-hop ego highlight + inspector)** | `design/references/knowledge-spatial.md` |
| *Is HOURGLASS safe, calibrated, and paper-only?* | 5 risk bands, 4 readiness gates, 7-stage pipeline, Brier scores | **5-Band Risk Stack + 7-Stage Pipeline Stepper + Brier Comparison Table** | `design/references/quant-financial.md` |
| *What changed between valid time and transaction time?* | Append-only hash-chained ledger events (`v2`) | **Bitemporal Receipt Card + Provenance Badge (`observed` / `oracle_taste`)** | `design/references/temporal-bitemporal.md` |
| *Did the candidate beat the baseline across seeds?* | N runs × metrics × seeds/CI | **Paired Delta / Ablation Table with `tabular-nums` + Regime Ribbon** | `design/references/ml-experiment-viz.md` |

## Step 2 — Enforce Honest Missingness & Epistemic Labels

1. **Never emit blanket `"UNKNOWN"` badges.** Every metric or producer state must distinguish:
   - `0` — producer ran and observed zero items (render `0` in `--fg-primary`).
   - `unmeasured` — optional producer or telemetry source is not configured (render muted `unmeasured` chip with explicit reason, e.g., `no account producer`).
   - `stale` / `drift` — producer data exists but lags workspace HEAD or window (render `--status-warning` pill).
   - `failed` — producer or verifier ran and returned an error (render `--status-danger` pill with error summary).
   - `observed` / `inferred` / `synthesized` / `proposed` / `oracle_taste` — epistemic status per `AGENTS.md` Rule 3.
2. **Ban `<dl>` Key-Value Slop.** Do not dump multi-record arrays into nested `<dl><dt><dd>` lists. Use `<table>` with `font-variant-numeric: tabular-nums` for multi-record comparisons and `.kv-grid` cards for bounded metadata (≤ 6 pairs).

## Step 3 — Interactive SVG & Canvas Rules

- Every interactive SVG node or edge (`role="button"`, `tabindex="0"`) must respond to both `click` and keyboard `Enter` / `Space`.
- Provide explicit viewport controls (`Pan ←/↑/↓/→`, `Zoom +`, `Zoom −`, `Fit View`) and 1-hop ego highlighting (`data-ego="active"|"dim"`) on spatial canvases.
- Compute `viewBox` dynamically from the bounding box of all rendered neighborhoods and event nodes so 200+ events never clip outside the viewport.

## Companion Skills
- Preceded by `[[lab-ui-plan]]` (screen brief & topology graph).
- Implemented with `[[lab-ui-build]]` (`SHARED TOKENS v1` & CSS architecture).
- Verified by `[[lab-ui-review]]` (`python3 design/scripts/qa_gate.py`).
- Distilled via `[[trace-and-distill]]` (`design/scripts/record_agent_trace.py`).
