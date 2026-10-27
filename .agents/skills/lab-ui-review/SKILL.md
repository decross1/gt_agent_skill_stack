---
name: lab-ui-review
description: Run the blocking deterministic UI/UX QA gate (design/scripts/qa_gate.py) followed by a structured 4-pass critique (Epistemic & Missingness Honesty, Representation Fit, Tufte Data-Ink & Typography, Accessibility & Security). Use to audit any UI change before shipping or merging.
layer: B
runtime-safe: false
pack: design
---

# `lab-ui-review` — Blocking Deterministic QA Gate & 4-Pass UI Critique

## When to Use
Invoke `lab-ui-review` after `[[lab-ui-build]]` and before `[[ship]]` or `[[trace-and-distill]]` whenever any HTML, CSS, SVG, or frontend JS/TS file is added or modified. Never rely on unpaginated LLM self-praise; run the deterministic gate first.

## Stage 1 — Blocking Deterministic QA Gate (`qa_gate.py`)

Run `design/scripts/qa_gate.py` against the local HTML bundle (and live loopback URL if serving):
```bash
python3 design/scripts/qa_gate.py <path-to-index.html> --reharness-qual
```

**Hard Pass Criteria (all required):**
1. `passed == true`
2. `unknown_badge_ratio <= 0.05` (no raw `"UNKNOWN"` badge spam; missing producers must render `unmeasured` with reason).
3. `dl_term_count <= 24` (no raw `<dl><dt><dd>` key-value dumps for multi-record tables or KPI strips).
4. `external_cdn_count == 0` (zero external font/script/stylesheet URLs).
5. `missing_css_token_count == 0` and `tabular_nums == true` (`SHARED TOKENS v1` compliance).
6. `has_main == true`, `tab_count == tabpanel_count`, and `overflow_px == 0`.

Also run the repository's contract tests (e.g., `pytest tests/test_portal_view.py tests/test_portal_ui.py tests/test_ui_release.py`). If any check fails, block sign-off and return to `[[lab-ui-build]]`.

## Stage 2 — Structured 4-Pass Critique

Once `qa_gate.py` passes, perform a concise 4-pass inspection:
1. **Pass 1 — Epistemic & Governance Honesty**:
   - Are `observed`, `inferred`, `synthesized`, `proposed`, `oracle_taste`, and `unmeasured` states visually distinct?
   - On financial/execution views (`#tab-hourglass`), is the `PAPER / DRY-RUN ONLY — Capital Execution Human-Gated (AGENTS.md Rule 6)` banner immediately visible?
2. **Pass 2 — Munzner Representation Fit (`[[agent-viz]]`)**:
   - Does each card/table/canvas answer its operator question in ≤ 5 seconds?
   - Are spatial graphs equipped with pan/zoom/fit controls, 1-hop ego highlighting, and keyboard-operable (`Enter`/`Space`) inspectors?
   - Are quota envelopes rendered with visual bullet bars (`.bullet-track`/`.bullet-fill`/`.bullet-floor-tick`) rather than text-only cells?
3. **Pass 3 — Tufte Data-Ink & Typography**:
   - Are numbers aligned with `font-variant-numeric: tabular-nums`?
   - Are table cells free of redundant repeated column-header prefixes?
4. **Pass 4 — Security & Failure Recovery**:
   - Are all server/vault strings rendered via `textContent` (never `innerHTML`)?
   - On form submission error or partial mirror/cache write, is the user's draft preserved?

## Handoff
Feed the `qa_gate.py` JSON report and 4-pass critique findings into `[[trace-and-distill]]`.
