---
name: lab-ui-build
description: Build high-density, token-compliant research-lab interfaces using SHARED TOKENS v1, Tufte tabular typography, accessible keyboard navigation, and zero external CDN dependencies. Use when writing or refactoring HTML, CSS, SVG, or frontend JS/TS across Oracle (:8790, :8765), Nara (:5173), or Brain (:5180).
layer: B
runtime-safe: false
pack: design
---

# `lab-ui-build` — Token-Compliant Research-Lab UI Craft

## When to Use
Invoke `lab-ui-build` when implementing or refactoring any web UI, static HTML/CSS/JS view, or component in `oracle_system`, `a_bgt_rsi`, or `agent_system` after completing `[[lab-ui-plan]]` and `[[agent-viz]]`.

## Core Implementation Rules

### 1. Token Discipline (`SHARED TOKENS v1`)
- Copy or import the exact `:root, [data-theme="dark"]` custom property block from `design/system.md` (`--bg-canvas`, `--bg-surface-1`, `--bg-surface-2`, `--fg-primary`, `--fg-secondary`, `--accent-primary`, `--status-success`, `--status-warning`, `--status-danger`, `--font-sans`, `--font-mono`, spacing and radius scales).
- Never hardcode ad-hoc hex colors in component rules when a semantic token exists.
- Enforce `font-variant-numeric: tabular-nums` on all `<code>`, `<pre>`, `<td>`, KPI readouts, commit SHAs, ports, and financial/Brier metrics.

### 2. Anti-Slop DOM & Security Hygiene
- **Zero `innerHTML` with untrusted/server strings**: build DOM nodes via `document.createElement` / `textContent` and `document.createElementNS` for SVG so vault notes, error strings, and tags cannot trigger XSS.
- **Zero External CDNs**: never link external Google Fonts, unpkg, or jsDelivr assets. All views must work offline on `127.0.0.1` and private Tailscale CGNAT (`100.64.0.0/10`) without external network fetches.
- **Dynamic Host Links**: derive cross-surface links (`:5173`, `:5180`, `:8765`, `:8790`) from `window.location.origin` / `window.location.hostname` — never hardcode `localhost`.
- **Single-Root Release Marker**: in `oracle_system`, `RELEASE.json` is written only at `source_root / "RELEASE.json"` (never inside `frontend_dir`), preserving `tools/pinned_paths.py` snapshot verification.

### 3. Tufte High-Density Layout & Honest State Taxonomy
- Replace repetitive `<dl><dt><dd>` dumps with `.kpi-grid` metric cards (top-level summary), `.portal-table` aligned tables (multi-row records, without repeating column header labels inside each `<td>`), or `.kv-grid` cells (≤ 6 bounded metadata attributes).
- Render quota envelopes with visual `.bullet-track`, `.bullet-fill`, and `.bullet-floor-tick` bars paired with tabular-nums readouts.
- Map status values through a deterministic tone classifier (`healthy`, `warning`, `danger`, `info`, `neutral`) and format missing optional producers as `unmeasured` rather than raw `"UNKNOWN"`.
- Preserve backward-compatible error banners (`UNKNOWN / unavailable`) where contract tests assert exact fallback substrings on network failure.

### 4. Accessibility & Keyboard Operability
- Provide `<a class="skip-link" href="#portal-main">Skip to content</a>`, `<main id="portal-main">`, and `aria-live="polite"` status regions.
- Implement WAI-ARIA tabs (`role="tablist"`, `role="tab"`, `role="tabpanel"`, `ArrowRight`/`ArrowLeft`/`Home`/`End` focus roving) and `Enter`/`Space` activation on interactive SVG elements.

## Pre-Handoff Self-Check
Before handing off to `[[lab-ui-review]]`, run:
```bash
python3 design/scripts/qa_gate.py <path-to-index.html>
```
Verify `passed: true`, `unknown_badge_ratio <= 0.05`, `dl_term_count <= 24`, and `external_cdn_count == 0`.
