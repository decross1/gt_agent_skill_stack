# Canonical Design System (`design/system.md`)

**Status:** Single authoritative record of tokens, typography, semantic state encodings, information density, and interaction rules across `agent_system`, `oracle_system`, and `a_bgt_rsi`.
**Token Parity Verifier:** `scripts/check_design_tokens.py`

---

## 1. Canonical Color & Surface Tokens

All dark-mode analytical surfaces across the lab (`memory/brain/view/tokens.css`, `a_bgt_rsi/ui/frontend/src/tokens.css`, `oracle_harness/portal_view/styles.css`, and `cockpit.html`) anchor to the shared v1 token block:

```css
/* ====== BEGIN SHARED TOKENS v1 (synced copy; checked by scripts/check_design_tokens.py) ====== */
:root {
  --bg:#09090b; --surface:#18181b; --surface-2:rgba(24,24,27,.4);
  --border:#27272a; --border-2:#3f3f46;
  --text:#e4e4e7; --text-dim:#a1a1aa; --text-faint:#71717a; --text-ghost:#52525b;
  --accent:#10b981; --ok:#34d399; --warn:#fbbf24; --bad:#f87171; --idle:#38bdf8;
  --ok-bg:#022c22; --warn-bg:#451a03; --bad-bg:#450a0a;
  --agent-nara:#34d399; --agent-coordinator:#7dd3fc; --agent-workflow:#a5b4fc;
  --agent-claude:#c084fc; --agent-human:#a1a1aa; --agent-nemoclaw:#a78bfa; --agent-other:#fda4af;
  --font-mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
}
/* ====== END SHARED TOKENS v1 ====== */
```

### Extended Semantic & Epistemic Tokens (Per-Surface Layer)

When a surface renders fleet agents (`argon`, `codex`, `opus`, `sonnet`) or epistemic provenance badges, extend `:root` *outside* the `SHARED TOKENS v1` marker block using these canonical names:

```css
:root {
  --bg-canvas: var(--bg);
  --bg-surface-1: var(--surface);
  --bg-surface-2: var(--surface-2);
  --fg-primary: var(--text);
  --fg-secondary: var(--text-dim);
  --accent-primary: var(--accent);
  --status-success: var(--ok);
  --status-warning: var(--warn);
  --status-danger: var(--bad);
  --font-sans: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  --surface-elevated: #1f1f23;
  --surface-interactive: #27272a;
  --idle-bg: #082f49;
  --accent-bg: rgba(16, 185, 129, 0.14);

  /* Fleet Agent Identity Colors */
  --agent-argon: #38bdf8;
  --agent-codex: #34d399;
  --agent-opus: #c084fc;
  --agent-sonnet: #fbbf24;

  /* Epistemic Provenance Encodings */
  --epistemic-observed: #34d399;      /* Solid border, high-confidence empirical */
  --epistemic-inferred: #38bdf8;      /* Dashed border, rule-derived */
  --epistemic-synthesized: #a5b4fc;   /* Dotted/double border, cross-source */
  --epistemic-taste: #f472b6;         /* Accent pill, owner curiosity/resonance */
  --epistemic-unmeasured: #71717a;    /* Muted neutral, not instrumented */
}
```

---

## 2. Typography & Visual Hierarchy

1. **Font Stacks:**
   - `--font-sans` for prose, titles, explanations, and navigation.
   - `--font-mono` for commit SHAs, timestamps, IDs (`D-056`, `evt_sha256_...`), metric values, kill codes, and file locators.
   - Apply `font-variant-numeric: tabular-nums` to all numeric columns, counters, percentages, timestamps, and payoff matrices so vertical alignment never jitters.
2. **Type Scale & Density (Tufte Anti-Slop Discipline):**
   - **Page Title / Primary Question Header:** `1.125rem` (`18px`), `font-weight: 600`, tight tracking (`-0.01em`), paired on the same row with global status strip and freshness indicator.
   - **Section / Panel Header:** `0.875rem` (`14px`), `font-weight: 600`, accompanied by a 1-sentence subtitle or metric summary.
   - **Body / Table Cell:** `0.8125rem` (`13px`), `line-height: 1.45`, comfortable reading width (`55ch–75ch` for prose).
   - **Micro Metadata / Provenance Pill / Axis Tick:** `0.75rem` (`12px`), `--text-dim` or `--text-faint`. Never drop below `11px`.
3. **High Data-Ink Ratio:**
   - Eliminate decorative marketing cards, unmotivated gradients, oversized hero banners, and redundant labels.
   - Prefer **compact status strips**, **aligned comparison tables**, **sparklines/bars embedded in table rows**, **2D spatial canvases**, and **master-detail split panes** over grids of giant low-density cards.
   - Group related metrics into a single structured table or horizontal strip rather than spawning a separate card per number.

---

## 3. Explicit Visual Meaning & Redundant Encoding

Never rely on color alone to communicate consequential state:

| State | Color Token | Shape / Border / Icon | Label Rule |
|---|---|---|---|
| **`healthy` / `match` / `passed`** | `--ok` (`#34d399`) on `--ok-bg` | Solid pill, `●` or `✓` | Concise state (`Healthy`, `In Sync`, `Passed`) |
| **`stale` / `behind` / `warning`** | `--warn` (`#fbbf24`) on `--warn-bg` | Dashed border, `◐` or `⚠` | Include delta (`2 commits behind`, `Stale · 4h`) |
| **`failed` / `degraded` / `blocked`** | `--bad` (`#f87171`) on `--bad-bg` | Heavy left border (`3px solid var(--bad)`), `✕` | Include specific reason or kill code |
| **`running` / `active` / `in_progress`** | `--idle` (`#38bdf8`) on `--idle-bg` | Subtle pulse or `▸` | Include elapsed time or active step |
| **`unmeasured` / `not_tracked`** | `--text-faint` (`#71717a`) | Muted pill, no alarm fill | Explain why (`Not instrumented`, `Passive only`) |
| **`0` (Explicit Zero)** | `--text-dim` (`#a1a1aa`) | Explicit `0` glyph + baseline tick | Never render `0` as empty, `—`, or `UNKNOWN` |

---

## 4. Layout, Progressive Disclosure & Interaction Rules

1. **Three-Tier Progressive Disclosure:**
   - **Tier 1 — Global Liveness & Attention Strip (Top Bar):** Answers *"Is the system healthy and in sync right now?"* in `<48px` vertical height (5-pipe pills, 4-surface release drift badge, active alert count).
   - **Tier 2 — Primary Analytical / Spatial Workspace:** Answers the active tab's primary question (e.g., 2D Essence Atlas canvas + neighborhood list; Fleet Coordination matrix + mail stream; Evidence Ladder funnel + run comparison).
   - **Tier 3 — Linked Inspector Drawer / Detail Pane:** Selecting any node, pipe, agent, event, or experiment opens its full provenance, raw fields, validity interval (`valid_from` → `valid_to`), and source links without losing scroll position or canvas viewport state.
2. **Layout Stability During Live Refresh:**
   - Polling or WebSocket refreshes must update data in place and preserve:
     - Active tab / route hash
     - Selected entity ID (`selectedNodeId`, `selectedAgent`, `selectedPipeId`)
     - Search/filter inputs and scroll offsets
     - Spatial canvas pan/zoom transform (`panX`, `panY`, `zoom`)
3. **Responsive & Viewport Discipline (`390px` Mobile & `1280px` Desktop):**
   - Use CSS Grid (`grid-template-columns: repeat(auto-fit, minmax(...))`) and Flexbox with `min-width: 0` on flex/grid children so long hashes or paths truncate or wrap cleanly without horizontal page overflow (`document.documentElement.scrollWidth <= window.innerWidth`).
   - At `390px` (mobile / Tailscale phone inspection), split panes collapse cleanly into stacked panels with touch-friendly targets (`>= 36px` height).
4. **Accessibility & Keyboard Navigation:**
   - Every interactive control (`<button>`, `[role="tab"]`, canvas node, filter chip) must be keyboard-focusable (`:focus-visible` ring using `2px solid var(--accent)`).
   - Provide `prefers-reduced-motion: reduce` fallbacks for all transitions and animations.
   - Include explicit `loading`, `empty`, `partial-data`, `stale-data`, and `error` states on every data-driven panel.
