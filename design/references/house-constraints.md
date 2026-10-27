# House Constraints & Craft Base (`design/references/house-constraints.md`)

## When to use
Loaded by `lab-ui-build` and `lab-ui-review` on **every** UI/UX implementation or review task across `agent_system` (`:5180`), `oracle_system` (`:8790`, `:8765`), and `a_bgt_rsi` (`:5173`). Combines upstream craft practices (`Interface Design`, `Impeccable`, `Vercel Web Design Guidelines`) with our lab's strict portability, Tufte information-density, and deterministic QA gate rules.

## Data contract
Every rendered view must bind to an explicit backend payload or static fixture and expose:
- **Release & freshness metadata:** commit hash (`running_commit` vs. `target_commit`) and `generated_at` / `observed_at` ISO-8601 timestamp.
- **Epistemic provenance:** `observed`, `inferred`, `synthesized`, `proposed`, `speculative`, `oracle_taste`, or `unknown` (`AGENTS.md` Rule 3).
- **Distinct non-nominal states:** `0` (explicit zero), `unmeasured` (not instrumented), `stale` (exceeded freshness window), `failed` (check ran and failed), and `unknown` (unexpected missing state).

## Canonical views & layout rules
1. **Control Panel vs. Spatial/Analytical Workspace:**
   - Top bar (`<48px` height): global status pills (e.g., 5-pipe continuity strip, 4-surface release sync badge, freshness age, search/filter controls).
   - Main workspace: CSS Grid / Flexbox layout (`min-width: 0` on all children) combining a primary visual representation (2D canvas, timeline, funnel, aligned comparison table) with a linked detail/inspector drawer.
2. **Self-Contained / Zero-External-CDN Portability:**
   - Standalone views (`memory/brain/view/*.html`, `oracle_harness/portal_view/`, `cockpit.html`) must use **zero external CDN scripts, stylesheets, or remote fonts**. Offline/Tailscale/sandboxed environments must render identically.
   - Charts use inline SVG (with explicit `viewBox` and bounded coordinates) or HTML5 Canvas / server-side base64 figures.
3. **Static / Exported Figure Spec:**
   - Aspect ratio `4:3` (`7 × 5.25 in` at `200 DPI`), base font `>= 13pt`, tick labels `>= 12pt`, title `>= 15pt`, `<= 6` x-axis ticks, direct series labels or bottom legend.

## Interactions
- **Selection linkage:** Clicking a row, node, or bar highlights related items across views and populates the inspector pane without losing scroll position or canvas pan/zoom.
- **Keyboard & focus:** All interactive elements must be reachable via `Tab`, activate on `Enter`/`Space`, close drawers on `Escape`, and show a `2px solid var(--accent)` `:focus-visible` outline.
- **Responsive breakpoints:** Must render with zero horizontal overflow (`scrollWidth <= innerWidth`) at both `390px` (mobile/Tailscale) and `1280px` (desktop).

## Anti-patterns
- **Don't** dump raw Python/JSON dicts into `<dl><dt>key</dt><dd>value</dd></dl>` walls; **do** group related attributes into aligned tabular columns, compact badges, or progressive detail drawers.
- **Don't** render missing or uninstrumented fields as alarming `"UNKNOWN"` badges across every card; **do** distinguish `0`, `unmeasured` (`"Not instrumented"`), `stale`, and `failed`.
- **Don't** use generic 3-card marketing rows or decorative gradients; **do** maximize Tufte data-ink ratio (`tabular-nums`, inline bars, dense comparison rows).
- **Don't** import external CDN libraries (`unpkg.com`, `cdn.jsdelivr.net`, `googleapis.com`) in standalone lab views; **do** use self-contained CSS/JS and inline SVG/Canvas.

## Deterministic checks
Enforced by `python3 design/scripts/qa_gate.py`:
1. `tag_balance`: HTML open/close tags balance cleanly.
2. `no_external_cdn`: Zero `http://` or `https://` `<script src>` / `<link href>` / `@import` URLs in standalone views.
3. `shared_tokens_present`: Uses canonical `--bg`, `--surface`, `--text`, `--ok`, `--warn`, `--bad`, `--font-mono` tokens from `design/system.md`.
4. `svg_bounds`: Every `<svg>` declares a valid `viewBox` or explicit dimensions with finite coordinates.
5. `anti_slop_unknown_ratio`: Count of raw `"UNKNOWN"` badge strings is `<= 5%` of rendered data cells and never used for uninstrumented optional fields.
6. `anti_slop_dl_dump`: Rejects pages where raw `<dl>` key-value pairs exceed threshold without structured tables or visual encodings.
7. `viewport_overflow` (when browser probe enabled): `scrollWidth <= clientWidth` at `390px` and `1280px`.

## Sources
- `Dammyjay93/interface-design` (hierarchy & `.interface-design/system.md` persistence, reviewed `2026-10-27`)
- `pbakaus/impeccable` (critique, distill, harden & detector rules, reviewed `2026-10-27`)
- `vercel-labs/agent-skills` (`web-design-guidelines` accessibility & interaction rules, reviewed `2026-10-27`)
- Edward Tufte, *The Visual Display of Quantitative Information* (data-ink ratio & small multiples)
