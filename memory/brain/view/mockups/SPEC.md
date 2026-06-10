# SPEC — brain governance dashboard + graph (synthesis of m1/m2/m3)

Verdict 2026-06-10: **m1 "stack" wins** (24/25; m2 rail 19; m3 immersive 5 — m3 ships a
script-killing syntax error: the `*/` inside the path-glob block comment at m3.html:267
aborts the whole script, page renders blank). Build `dashboard.html` from m1, lifting the
cited lines verbatim; graft the m2/m3 pieces listed below. `graph.html` is the "Map" nav
target: same paint/edge/hover spec, full-viewport, fully live (hover + click-select).
Keep the SHARED TOKENS v1 block (m1.html:8-19) byte-identical — checked by
`scripts/check_design_tokens.py`. All rendering is data-driven from the DATA object.

## 1. Landing layout (dashboard.html, tuned at 1440x900)
Band order (m1.html:162-228): header 56px → status strip 46px → inbox (min-height 188px,
grid `1fr / minmax(380px,40%)`) → map band 55vh (min 430px) with 300px side panel →
glyph-only legend 30px → fold. The "loop" band label lands at ~900px as the scroll hint.
- Header (m1.html:162-171): brand "brain · governance" · Dashboard/Map pill nav · spacer ·
  7-tick window stepper · mono as-of date · "apparatus →" cross-nav.
- Status strip (m1.html:336-366): 6 equal segments, each title-tooltipped —
  amber dot + "attention" / NEEDS YOU n + severity spark (3 bars 10/7/4px in bad/warn/idle,
  m1.html:348) / DRIFT n / LOOP ◐ state·days / FW ✓ / FRESH nd.
  Graft: m2's conic-gradient half-dormant dot for the LOOP glyph (m2.html:56).

## 2. Needs-you inbox
Sort by severity rank; head item becomes the one-decision card in the right column; the rest
render as grouped one-liners: sev dot · mono kind · ×count pill · ellipsized title · age
(m1.html:368-397). Row tooltip carries its cmd. Card: red-tint border rgba(248,113,113,.32),
kind colored --bad, title line, mono cmd box.
- Graft: m2's explicit `copy` text button (m2.html:335) instead of the bare ⧉ glyph; keep
  m1's ✓-for-1.1s feedback (m1.html:394-396).
- Empty state "nothing needs you", wired to `DATA.inbox.length` (m1.html:372).
- graph.html may use m3's severity chips→overlay toggle (m3.html:304-328) to save chrome.

## 3. Cluster map — m1 hulls (not lanes, not radial)
SVG `viewBox 0 0 1080 500`, xMidYMid meet (m1.html:187). Hand-tuned SPOS/APOS positions
(m1.html:299-310). Hull algorithm — lift verbatim m1.html:405-426: monotone-chain convex
hull per pack → push each vertex 30px radially from the pack centroid → close with quadratic
curves through edge midpoints → fill var(--surface) opacity .55, stroke var(--border) .8;
pack label above the region's min-Y. Agent radius `7 + 1.7*sqrt(runs)` (m1.html:315);
human:decross1 is a rotated-square diamond (m1.html:481-483).
- Graft (mandatory): m2's label halos on ALL svg text — `paint-order:stroke; stroke:#09090b;
  stroke-width:3px; stroke-linejoin:round` (m2.html:121). This is m1's one legibility gap.
- Graft: m3's debounced resize→rebuild (m3.html:551) once positions are computed at runtime.

## 4. Node paint (exactly m1.html:449-491; radii in viewBox units)
Base skill node r7, fill --surface, stroke --border-2 w1.2. Stacked state rings:
- drift: r15 --warn w4 opacity .12 + r11.5 --warn w1.3 opacity .85 (m1.html:454-457)
- healed: r16 --ok w5 op .08 + r12.5 --ok w1.3 pulsing (m1.html:458-461). Replace m1's
  opacity-blink with m3's radar ping — scale 1→1.55 fading ring, `transform-box:fill-box;
  transform-origin:center` (m3.html:44-45) — and KEEP m1's prefers-reduced-motion
  fallback (m1.html:95).
- fresh: r9.5 dashed #fff w1 op .65, dash `2.5 3` (m1.html:462-463)
- ref-only (by_design): group opacity .4 + dashed 5×5 square tag at (8,-13) + tooltip
  "referenced-only, by design" (m1.html:467-468)
- runtime-safe: inner ring r3.2 --accent w1.3 op .95 (m1.html:465-466)
- selected: r17 ring --text-dim op .5 (m1.html:453)
- zero-attribution agent: group op .45, dashed stroke, "awaiting attribution" hint text
  below the label (m1.html:479-488).

## 5. Edges (m1.html:429-440, verbatim)
Quadratic curve; control point = midpoint offset perpendicular by `0.07*dist`; trim ends to
node radii (agent r+5, skill 17). Stroke = agent hue, opacity .55, linecap round.
Width `1 + 2*sqrt(e+i)`. `e===0` → dashed, dash scaled to width: `${2+w} ${3.5+w}`.
Per-edge `<title>`: "agent → skill · e# i# · explicit|inferred only". Keep the fat
coordinator→run-log (~12.5px) — the hammered core IS the story.

## 6. Side panel (300px; statically open on run-log in dashboard.html; m1.html:517-557)
Blocks in order:
1. head — mono skill name + pack chip + `runtime-safe` emerald chip + `drift` warn chip
2. USAGE — legend (solid dot=explicit, hollow=inferred) then per-agent rows: hue dot · id ·
   split bar (e solid at agent hue, i at agent hue opacity .32 — NOT m2's gray) · mono "e#·i#"
3. PROPOSAL — id row + `open` warn pill
4. conformance note "▲ friction ×3 · diverged ×1" (tooltip → memory/conformance.md)
- graph.html: make it live with m3's click-to-select — dashed selection ring +
  `renderPanel(name)` rebuild + ✕ close (m3.html:457-464, 483-514).

## 7. Hover card (m1.html:494-514)
Skill card: mono name / "pack · states" subline / one row per using agent: hue dot +
"agent · e# i#". Agent card: mono id / "runs / windowd" / top-4 skills by e+i.
Position: cursor +14,+12 with edge flip (m1.html:498-501). graph.html pins one card on load
as the affordance demo (m2.html:434-436 pattern, getScreenCTM positioning).

## 8. Below the fold (m1.html:559-606; order fixed)
loop strip → contracts → timeline → rules → footer.
- loop: `harvest n ◐dormant → proposals n open → review ✓n ✗n → enacted n rules · n skills`,
  arrow-joined segments, each tooltipped (m1.html:561-574).
- contracts: id · agent hue dot+name · pass|freeform pill · mono budget · age (m1.html:576-585).
- timeline: date · kind colored (proposal --idle, correction --bad, decision --accent,
  reflection --text-faint) · id · ⚑ + red row tint for flagged (m1.html:153, 587-597) ·
  agent hue dot. Compact-mode graft: m2's drawer — one-line bar with 6 agent-hue dots,
  click-to-expand rows (m2.html:230-238, 456-467).
- rules: id · text · ×n warn badge, or "—" when n=0 (m1.html:599-605).
- footer: `schema v2 · generated <date> · apparatus →`.

## 9. Window stepper
7 ticks: current window `.on` (emerald), ticks below it `.fill`, digits only on 1 and 7
(m1.html:325-333). v1 is visual-only with tooltip "window: last 7 days (visual only)".
When live: clicking tick k re-queries a k-day window and re-renders strip, map, and panel
from DATA — never navigates.

## 10. Anti-verbosity contract
Above-fold budget <120 words at 1440x900 (tokens containing an alphanumeric; m1 measures
119 by uniform DOM count). Explanations live exclusively in `title=` tooltips — zero visible
prose paragraphs; legend stays glyph-only (m1.html:195-204). Two build-hygiene rules from
the losers: never put a path glob inside a JS block comment (m3.html:267 killed the page),
and never leave non-HTML artifacts in the body (m2.html:180-181).
