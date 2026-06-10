// map.js — BrainMap: the agent ↔ skill governance cluster map (canvas).
// Frozen embed contract (dashboard.html + graph.html both rely on it):
//   BrainMap.mount(canvasEl, { summary: window.BRAIN_SUMMARY, map: window.BRAIN_MAP,
//                              windowDays: n, embedded: bool, onSelect: (node)=>{} })
// embedded:true = compact dashboard mode (hover card on, click -> onSelect; the
// page owns any legend). Data: BRAIN_MAP {generated_at, nodes, edges, cards};
// paint states + windowed usage come from BRAIN_SUMMARY when present.
// Layout per mockups/SPEC.md §3 (m1 hulls): hand-tuned anchors in a 1080x500
// world, local repulsion + spring + radius clamp, converge <120 frames, idle.
(function () {
"use strict";

const VW = 1080, VH = 500;
// Hand-tuned world positions (SPEC §3, m1.html:299-310). Skills missing here
// (future packs) fall back to a ring around their pack's centroid.
const SPOS = {
  "fallback": [392, 150], "resume-state": [514, 148], "run-log": [436, 234], "validate": [336, 300],
  "gate-check": [484, 312], "spawn-contract": [566, 252], "slip-ladder": [352, 356],
  "experiment": [740, 92], "code-review": [842, 66], "investigate": [940, 90], "plan-research": [748, 172],
  "ship": [848, 146], "health": [958, 162], "repro-check": [818, 224], "auto-experiment": [922, 234],
  "narrate": [906, 322], "propose": [998, 310], "brain-recall": [914, 398], "review-proposal": [1002, 386],
  "decision-log": [660, 356], "harvest": [744, 326], "orchestrate": [704, 412], "context-save": [618, 404], "context-restore": [788, 400]
};
const APOS = {
  "claude-code-main": [296, 84], "nara": [116, 246], "coordinator": [138, 398],
  "workflow": [412, 446], "human:decross1": [640, 464], "integrator": [84, 60], "nemoclaw_agent": [84, 60]
};
// Token fallbacks so the canvas still paints if tokens.css fails to load.
const FB = {
  "--bg": "#09090b", "--surface": "#18181b", "--border": "#27272a", "--border-2": "#3f3f46",
  "--text": "#e4e4e7", "--text-dim": "#a1a1aa", "--text-faint": "#71717a", "--text-ghost": "#52525b",
  "--accent": "#10b981", "--ok": "#34d399", "--warn": "#fbbf24", "--bad": "#f87171", "--idle": "#38bdf8",
  "--agent-nara": "#34d399", "--agent-coordinator": "#7dd3fc", "--agent-workflow": "#a5b4fc",
  "--agent-claude": "#c084fc", "--agent-human": "#a1a1aa", "--agent-nemoclaw": "#a78bfa", "--agent-other": "#fda4af"
};
const _cc = {};
function col(name) {                       // "--x" | "var(--x)" | raw color
  const m = /^var\((--[a-z0-9-]+)\)$/i.exec(name);
  if (m) name = m[1];
  if (name[0] !== "-") return name;
  if (_cc[name]) return _cc[name];
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return (_cc[name] = v || FB[name] || "#fda4af");
}
function agentHue(id) {
  if (window.UI && window.UI.agentHue) return col(window.UI.agentHue(id));
  const K = { nara: "--agent-nara", coordinator: "--agent-coordinator", workflow: "--agent-workflow",
    "claude-code-main": "--agent-claude", integrator: "--agent-nemoclaw" };
  if (K[id]) return col(K[id]);
  if (String(id).indexOf("human:") === 0) return col("--agent-human");
  return col("--agent-other");
}
const esc = s => String(s == null ? "" : s)
  .replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
// Ego-ring glyph colors for non-skill/agent governance node types.
const TYPE_COL = { proposal: "--idle", rule: "--ok", harvest_finding: "#6366f1",
  spawn: "--agent-other", correction: "#a855f7", anomaly: "--bad", decision: "--accent" };
const REDUCED = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;

// shared chrome for the hover card + ego back button (token-driven)
(function injectCss() {
  if (document.getElementById("bm-style")) return;
  const t = document.createElement("style");
  t.id = "bm-style";
  t.textContent =
    ".bm-hover{position:absolute;display:none;pointer-events:none;z-index:30;background:var(--surface);" +
    "border:1px solid var(--border-2);border-radius:6px;padding:8px 10px;font-size:11px;min-width:160px;" +
    "max-width:280px;box-shadow:0 10px 28px rgba(0,0,0,.55);color:var(--text-dim);font-family:system-ui,sans-serif}" +
    ".bm-hover .hn{font-family:var(--font-mono);font-size:12px;color:var(--text)}" +
    ".bm-hover .hs{color:var(--text-faint);margin-top:2px}" +
    ".bm-hover .hr{display:flex;gap:8px;margin-top:3px;color:var(--text-dim);font-family:var(--font-mono);font-size:10.5px;align-items:center}" +
    ".bm-hover .hd{width:6px;height:6px;border-radius:50%;flex:none}" +
    ".bm-back{position:absolute;top:10px;left:10px;z-index:31;cursor:pointer;font:11px var(--font-mono);" +
    "color:var(--text-dim);background:var(--surface);border:1px solid var(--border-2);border-radius:5px;padding:4px 10px}" +
    ".bm-back:hover{color:var(--text)}";
  document.head.appendChild(t);
})();

class BrainMap {
  static mount(canvas, opts) {
    if (canvas.__brainmap) canvas.__brainmap.destroy();
    const inst = new BrainMap(canvas, opts || {});
    canvas.__brainmap = inst;
    return inst;
  }

  constructor(canvas, opts) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.sum = opts.summary || null;
    this.map = opts.map || { nodes: [], edges: [], cards: {} };
    this.windowDays = opts.windowDays || 7;
    this.embedded = !!opts.embedded;
    this.onSelect = opts.onSelect || null;
    this.asof = ((this.sum && this.sum.window && this.sum.window.newest_event) ||
      (this.map.generated_at || "").slice(0, 10));
    this.cards = this.map.cards || {};
    this.byId = new Map(this.map.nodes.map(n => [n.id, n]));
    this.selected = null; this.hovered = null; this.drag = null;
    this.ego = null;                       // {focus, placed:Map, edges, more1, more2}
    this.frame = 0; this._raf = 0; this._last = 0; this._dirty = true;
    this._loop = this._loop.bind(this);    // bind BEFORE resize() schedules the first frame

    this._prepMain();
    this._dom();
    this._bind();
    this.resize();
    this._ensureLoop();
  }

  // ---- data prep ----------------------------------------------------------
  _inWin(d) {
    if (!d || !this.asof) return false;
    const dd = Math.round((Date.parse(this.asof) - Date.parse(String(d).slice(0, 10))) / 864e5);
    return dd >= 0 && dd < this.windowDays;
  }
  _cellWin(agent, skill) {                 // windowed e/i — summary by_day first
    const cells = (this.sum && this.sum.matrix && this.sum.matrix.cells) || [];
    const c = cells.find(x => x.agent === agent && x.skill === skill);
    if (c && c.by_day) {
      let e = 0, i = 0;
      for (const d in c.by_day) if (this._inWin(d)) { e += c.by_day[d].e || 0; i += c.by_day[d].i || 0; }
      return { e, i };
    }
    return null;
  }
  _prepMain() {
    const skillsMeta = {};
    ((this.sum && this.sum.skills) || []).forEach(s => skillsMeta[s.name] = s);
    this.skills = []; this.skillByLabel = new Map();
    const packPts = {};
    for (const n of this.map.nodes) {
      if (n.type !== "skill") continue;
      const meta = skillsMeta[n.label] || {};
      const g = meta.governance || {};
      const st =
        g.firewall_violation ? "firewall" :
        (g.drift && g.drift.active) ? "drift" :
        (g.healed && this._inWin(g.healed.accepted_at)) ? "healed" :
        (g.new && this._inWin(g.new.born)) ? "new" :
        g.referenced_only_by_design ? "by_design" :
        (g.state === "untested") ? "untested" : "ok";
      const s = { n, label: n.label, pack: n.pack || meta.pack || "?",
        state: st, rt: !!meta.runtime_safe, gov: g, x: 0, y: 0, ax: 0, ay: 0, rows: [] };
      this.skills.push(s); this.skillByLabel.set(n.label, s);
      (packPts[s.pack] = packPts[s.pack] || []).push(s);
    }
    // anchors: hand-tuned SPOS, else a ring around the pack centroid
    for (const pk in packPts) {
      const known = packPts[pk].filter(s => SPOS[s.label]);
      const cx = known.length ? known.reduce((a, s) => a + SPOS[s.label][0], 0) / known.length : 540;
      const cy = known.length ? known.reduce((a, s) => a + SPOS[s.label][1], 0) / known.length : 250;
      packPts[pk].forEach((s, k) => {
        const p = SPOS[s.label];
        if (p) { s.ax = p[0]; s.ay = p[1]; }
        else { const a = k * 2.4; s.ax = cx + Math.cos(a) * 46; s.ay = cy + Math.sin(a) * 46; }
        s.x = s.ax; s.y = s.ay;
      });
    }
    // agents: APOS slots, unknowns stack down the left edge
    this.agents = []; let slot = 0;
    const agentRunsByDay = {};
    ((this.sum && this.sum.agents) || []).forEach(a => agentRunsByDay[a.id] = a.runs_by_day || {});
    for (const n of this.map.nodes) {
      if (n.type !== "agent") continue;
      const p = APOS[n.label] || [70, 60 + (slot++) * 64];
      this.agents.push({ n, label: n.label, x: p[0], y: p[1], runs: 0, zero: true });
    }
    // main edges: agent->skill `used`, windowed when summary has the cell
    this.mainEdges = [];
    for (const e of this.map.edges) {
      if (e.type !== "used") continue;
      const A = this.agents.find(x => x.n.id === e.src);
      const S = this.skillByLabel.get((this.byId.get(e.dst) || {}).label);
      if (!A || !S) continue;
      const w = this._cellWin(A.label, S.label) || { e: e.weight_e || 0, i: e.weight_i || 0 };
      if (w.e + w.i <= 0) continue;
      const row = { a: A, s: S, e: w.e, i: w.i };
      this.mainEdges.push(row); S.rows.push(row);
    }
    for (const A of this.agents) {
      const rbd = agentRunsByDay[A.label];
      if (rbd) { for (const d in rbd) if (this._inWin(d)) A.runs += rbd[d]; }
      const mine = this.mainEdges.filter(m => m.a === A);
      if (!rbd || !A.runs) A.runs = Math.max(A.runs, mine.reduce((t, m) => t + m.e + m.i, 0));
      A.zero = !mine.length;
    }
    this.hasPulse = !REDUCED && this.skills.some(s => s.state === "healed");
  }
  _stateWords(s) {
    const W = { firewall: "firewall violation", drift: "drift", healed: "healed",
      new: "new", by_design: "ref-only by design", untested: "untested" };
    const w = [];
    if (W[s.state]) w.push(W[s.state]);
    if (s.rt) w.push("runtime-safe");
    return w;
  }

  // ---- dom + events -------------------------------------------------------
  _dom() {
    this.wrap = this.canvas.parentElement;
    if (getComputedStyle(this.wrap).position === "static") this.wrap.style.position = "relative";
    this.hov = document.createElement("div");
    this.hov.className = "bm-hover";
    this.wrap.appendChild(this.hov);
    this.back = document.createElement("button");
    this.back.className = "bm-back";
    this.back.textContent = "× back to map";
    this.back.style.display = "none";
    this.back.addEventListener("click", () => this.exitEgo());
    this.wrap.appendChild(this.back);
  }
  _bind() {
    this._onMove = e => this._move(e);
    this._onDown = e => this._down(e);
    this._onUp = e => this._up(e);
    this._onLeave = () => { this.hovered = null; this.hov.style.display = "none"; this._dirty = true; this._ensureLoop(); };
    this._onVis = () => { if (document.hidden) this._stopLoop(); else { this._dirty = true; this._ensureLoop(); } };
    this._onResize = () => { clearTimeout(this._rt); this._rt = setTimeout(() => { this.resize(); }, 150); };
    this.canvas.addEventListener("mousemove", this._onMove);
    this.canvas.addEventListener("mousedown", this._onDown);
    this.canvas.addEventListener("mouseleave", this._onLeave);
    window.addEventListener("mouseup", this._onUp);
    document.addEventListener("visibilitychange", this._onVis);
    window.addEventListener("resize", this._onResize);
  }
  destroy() {
    this._stopLoop();
    this.canvas.removeEventListener("mousemove", this._onMove);
    this.canvas.removeEventListener("mousedown", this._onDown);
    this.canvas.removeEventListener("mouseleave", this._onLeave);
    window.removeEventListener("mouseup", this._onUp);
    document.removeEventListener("visibilitychange", this._onVis);
    window.removeEventListener("resize", this._onResize);
    this.hov.remove(); this.back.remove();
    if (this.canvas.__brainmap === this) delete this.canvas.__brainmap;
  }
  resize() {                                // DPR-aware backing store; CSS owns the layout size
    const dpr = window.devicePixelRatio || 1;
    const w = this.canvas.clientWidth || this.wrap.clientWidth;
    const h = this.canvas.clientHeight || this.wrap.clientHeight;
    this.canvas.width = w * dpr; this.canvas.height = h * dpr;
    this.scale = Math.min(w / VW, h / VH);
    this.ox = (w - VW * this.scale) / 2; this.oy = (h - VH * this.scale) / 2;
    this.dpr = dpr; this._dirty = true; this._ensureLoop();
  }
  _world(e) {
    const r = this.canvas.getBoundingClientRect();
    return [(e.clientX - r.left - this.ox) / this.scale, (e.clientY - r.top - this.oy) / this.scale];
  }
  pick(wx, wy) {                            // nearest node under the cursor
    let best = null, bd = 1e9;
    const test = (x, y, r, ref) => {
      const d = (x - wx) ** 2 + (y - wy) ** 2;
      if (d < r * r && d < bd) { bd = d; best = ref; }
    };
    if (this.ego) {
      this.ego.placed.forEach(p => test(p.x, p.y, 16, { kind: "ego", p }));
      return best;
    }
    for (const A of this.agents) test(A.x, A.y, this._aR(A) + 6, { kind: "agent", a: A });
    for (const S of this.skills) test(S.x, S.y, 17, { kind: "skill", s: S });
    return best;
  }
  _aR(A) { return 7 + 1.7 * Math.sqrt(A.runs || 0); }

  _move(e) {
    const [wx, wy] = this._world(e);
    if (this.drag) {
      this.drag.x = Math.max(20, Math.min(VW - 20, wx + this.drag._dx));
      this.drag.y = Math.max(20, Math.min(VH - 20, wy + this.drag._dy));
      this.drag._moved = true; this._dirty = true; this._ensureLoop(); return;
    }
    const hit = this.pick(wx, wy);
    if (hit !== this.hovered) { this.hovered = hit; this._dirty = true; this._ensureLoop(); }
    if (hit) this._hoverCard(hit, e); else this.hov.style.display = "none";
    this.canvas.style.cursor = hit ? "pointer" : "default";
  }
  _down(e) {
    const [wx, wy] = this._world(e);
    const hit = this.pick(wx, wy);
    if (hit && hit.kind === "agent") {
      this.drag = hit.a; this.drag._dx = hit.a.x - wx; this.drag._dy = hit.a.y - wy;
      this.drag._moved = false; this.canvas.style.cursor = "grabbing";
    } else if (hit) this._select(hit);
    else { this.selected = null; this._dirty = true; this._ensureLoop(); }
  }
  _up() {
    if (this.drag) {
      if (!this.drag._moved) this._select({ kind: "agent", a: this.drag });
      this.drag = null; this._dirty = true; this._ensureLoop();
    }
  }
  _select(hit) {
    const node = hit.kind === "ego" ? hit.p.n : (hit.kind === "agent" ? hit.a.n : hit.s.n);
    this.selected = node;
    this._dirty = true; this._ensureLoop();
    if (this.onSelect) this.onSelect(node);
  }

  demoCard() {                              // SPEC §7: pin one hover card on load
    const s = this.skills.find(x => x.state === "drift") ||
              this.skills.find(x => x.rows.length) || this.skills[0];
    if (!s) return;
    const r = this.canvas.getBoundingClientRect();
    this._hoverCard({ kind: "skill", s }, {
      clientX: r.left + this.ox + s.x * this.scale,
      clientY: r.top + this.oy + s.y * this.scale
    });
  }

  _hoverCard(hit, e) {
    let html = "";
    if (hit.kind === "skill") {
      const s = hit.s, words = this._stateWords(s);
      const rows = s.rows.slice().sort((a, b) => (b.e + b.i) - (a.e + a.i)).map(m =>
        '<div class="hr"><span class="hd" style="background:' + agentHue(m.a.label) + '"></span>' +
        esc(m.a.label) + " · e" + m.e + " i" + m.i + "</div>").join("");
      const card = this.cards[s.n.id] || {};
      html = '<div class="hn">' + esc(s.label) + '</div><div class="hs">' + esc(s.pack) +
        (words.length ? " · " + esc(words.join(" · ")) : "") + "</div>" +
        (rows || '<div class="hs">no usage in window</div>') +
        (card.one_line ? '<div class="hs">' + esc(card.one_line.slice(0, 110)) + "</div>" : "");
    } else if (hit.kind === "agent") {
      const A = hit.a;
      const rows = this.mainEdges.filter(m => m.a === A).sort((x, y) => (y.e + y.i) - (x.e + x.i))
        .slice(0, 4).map(m => '<div class="hr">' + esc(m.s.label) + " · e" + m.e + " i" + m.i + "</div>").join("");
      html = '<div class="hn">' + esc(A.label) + '</div><div class="hs">' + A.runs + " runs / " +
        this.windowDays + "d</div>" + (rows || '<div class="hs">awaiting attribution</div>');
    } else {                                // ego node — card one-liner
      const n = hit.p.n, c = this.cards[n.id] || {};
      html = '<div class="hn">' + esc(c.title || n.label) + '</div>' +
        '<div class="hs">' + esc(n.type) + (c.date ? " · " + esc(c.date) : "") + "</div>" +
        (c.one_line ? '<div class="hs">' + esc(c.one_line) + "</div>" : "");
    }
    this.hov.innerHTML = html;
    this.hov.style.display = "block";
    const b = this.wrap.getBoundingClientRect();
    let hx = e.clientX - b.left + 14, hy = e.clientY - b.top + 12;
    if (hx + 290 > b.width) hx -= 310;
    if (hy + 120 > b.height) hy -= 140;
    this.hov.style.left = hx + "px"; this.hov.style.top = hy + "px";
  }

  // ---- ego mode (lineage): BFS <=2 hops, radial re-layout -------------------
  egoMode(id) {
    const focus = this.byId.get(id);
    if (!focus) return;
    const adj = new Map();
    const push = (a, b) => { (adj.get(a) || adj.set(a, []).get(a)).push(b); };
    for (const e of this.map.edges) { push(e.src, e.dst); push(e.dst, e.src); }
    const seen = new Set([id]);
    const ring = k => {                     // next hop, deterministic order
      const out = [];
      for (const cur of k) for (const nb of (adj.get(cur) || []))
        if (!seen.has(nb)) { seen.add(nb); out.push(nb); }
      return out.map(i => this.byId.get(i)).filter(Boolean)
        .sort((a, b) => (b.date || "").localeCompare(a.date || "") || a.id.localeCompare(b.id));
    };
    let h1 = ring([id]), h2 = ring(h1.map(n => n.id));
    const more1 = Math.max(0, h1.length - 22), more2 = Math.max(0, h2.length - 34);
    h1 = h1.slice(0, 22); h2 = h2.slice(0, 34);
    const placed = new Map();
    placed.set(id, { n: focus, x: VW / 2, y: VH / 2, hop: 0 });
    const SQ = 0.76;                        // vertical squash so hop-2 fits 500 world units
    const lay = (list, r, hop) => list.forEach((n, k) => {
      const a = -Math.PI / 2 + k * 2 * Math.PI / Math.max(list.length, 1);
      placed.set(n.id, { n, x: VW / 2 + Math.cos(a) * r, y: VH / 2 + Math.sin(a) * r * SQ, hop });
    });
    lay(h1, 132, 1); lay(h2, 226, 2);
    const eset = this.map.edges.filter(e => placed.has(e.src) && placed.has(e.dst));
    this.ego = { focus, placed, edges: eset, more1, more2 };
    this.back.style.display = "block";
    this.selected = focus;
    this._dirty = true; this._ensureLoop();
  }
  exitEgo() {
    this.ego = null;
    this.back.style.display = "none";
    this._dirty = true; this._ensureLoop();
  }

  // ---- simulation: local repulsion + spring to anchor + radius clamp --------
  _step() {
    const S = this.skills;
    for (let a = 0; a < S.length; a++) for (let b = a + 1; b < S.length; b++) {
      const A = S[a], B = S[b];
      let dx = A.x - B.x, dy = A.y - B.y, d2 = dx * dx + dy * dy;
      if (d2 < 1) { dx = 0.5; dy = 0.5; d2 = 1; }
      if (d2 > 8100) continue;              // local: ignore beyond 90 units
      const d = Math.sqrt(d2), f = 320 / d2;
      A.x += dx / d * f; A.y += dy / d * f; B.x -= dx / d * f; B.y -= dy / d * f;
    }
    for (const s of S) {
      s.x += (s.ax - s.x) * 0.08; s.y += (s.ay - s.y) * 0.08;
      const dx = s.x - s.ax, dy = s.y - s.ay, d = Math.hypot(dx, dy);
      if (d > 26) { s.x = s.ax + dx / d * 26; s.y = s.ay + dy / d * 26; }
    }
  }

  // ---- draw -----------------------------------------------------------------
  _loop(t) {
    this._raf = 0;
    if (document.hidden) return;
    const simming = this.frame < 120 && !this.ego;
    const pulsing = this.hasPulse && !this.ego;
    if (t - this._last >= 33 || simming) {  // ~30fps cap
      if (simming) { this._step(); this.frame++; }
      if (this._dirty || simming || pulsing) { this._draw(t); this._dirty = false; }
      this._last = t;
    }
    if (simming || pulsing || this._dirty || this.drag) this._ensureLoop();
  }
  _ensureLoop() { if (!this._raf && !document.hidden) this._raf = requestAnimationFrame(this._loop); }
  _stopLoop() { if (this._raf) { cancelAnimationFrame(this._raf); this._raf = 0; } }

  _text(x, y, txt, size, color, align) {    // m2 graft: dark halo behind every label
    const c = this.ctx;
    c.font = size + "px " + (align === "mono" ? "ui-monospace,Menlo,monospace" : "system-ui,sans-serif");
    c.textAlign = "center"; c.textBaseline = "middle";
    c.lineWidth = 3; c.lineJoin = "round"; c.strokeStyle = col("--bg");
    c.strokeText(txt, x, y); c.fillStyle = color; c.fillText(txt, x, y);
  }
  _ring(x, y, r, color, w, alpha, dash) {
    const c = this.ctx;
    c.save(); c.globalAlpha = alpha; c.strokeStyle = color; c.lineWidth = w;
    if (dash) c.setLineDash(dash);
    c.beginPath(); c.arc(x, y, r, 0, 2 * Math.PI); c.stroke(); c.restore();
  }

  _drawSkill(s, t) {
    const c = this.ctx, x = s.x, y = s.y;
    c.save();
    if (s.state === "by_design") c.globalAlpha = 0.4;
    else if (s.state === "untested") c.globalAlpha = 0.55;
    if (this.selected === s.n) this._ring(x, y, 17, col("--text-dim"), 1, 0.5, [4, 3]);
    if (s.state === "firewall") { this._ring(x, y, 15, col("--bad"), 4, 0.12); this._ring(x, y, 11.5, col("--bad"), 1.3, 0.85); }
    if (s.state === "drift") { this._ring(x, y, 15, col("--warn"), 4, 0.12); this._ring(x, y, 11.5, col("--warn"), 1.3, 0.85); }
    if (s.state === "healed") {
      this._ring(x, y, 16, col("--ok"), 5, 0.08);
      if (REDUCED) this._ring(x, y, 12.5, col("--ok"), 1.3, 0.5);
      else {                                 // m3 radar ping: ring scales 1->1.55 fading
        const ph = (t % 2200) / 2200;
        this._ring(x, y, 12.5, col("--ok"), 1.3, 0.85);
        this._ring(x, y, 12.5 * (1 + 0.55 * ph), col("--ok"), 1.2, 0.7 * (1 - ph));
      }
    }
    if (s.state === "new") this._ring(x, y, 9.5, "#ffffff", 1, 0.65, [2.5, 3]);
    c.beginPath(); c.arc(x, y, 7, 0, 2 * Math.PI);
    c.fillStyle = col("--surface"); c.fill();
    c.lineWidth = 1.2; c.strokeStyle = col("--border-2"); c.stroke();
    if (s.rt) this._ring(x, y, 3.2, col("--accent"), 1.3, 0.95);
    if (s.state === "by_design") {           // dashed ref-only tag
      c.save(); c.strokeStyle = col("--text-ghost"); c.setLineDash([1.6, 1.6]);
      c.strokeRect(x + 8, y - 13, 5, 5); c.restore();
    }
    this._text(x, y + 19, s.label, 10, col("--text-dim"));
    c.restore();
  }

  _drawAgent(A) {
    const c = this.ctx, r = this._aR(A), hue = agentHue(A.label);
    c.save();
    if (A.zero) c.globalAlpha = 0.45;
    c.beginPath();
    if (A.label.indexOf("human:") === 0) {   // rotated-square diamond
      c.save(); c.translate(A.x, A.y); c.rotate(Math.PI / 4);
      c.rect(-r * 0.78, -r * 0.78, r * 1.56, r * 1.56); c.restore();
    } else c.arc(A.x, A.y, r, 0, 2 * Math.PI);
    c.save(); c.globalAlpha *= 0.13; c.fillStyle = hue; c.fill(); c.restore();
    c.lineWidth = 1.6; c.strokeStyle = hue;
    if (A.zero) c.setLineDash([3, 3]);
    c.stroke(); c.setLineDash([]);
    if (this.selected === A.n) this._ring(A.x, A.y, r + 6, col("--text-dim"), 1, 0.5, [4, 3]);
    this._text(A.x, A.y + r + 14, A.label, 10, col("--text-dim"), "mono");
    if (A.zero) this._text(A.x, A.y + r + 26, "awaiting attribution", 8.5, col("--text-ghost"));
    c.restore();
  }

  _edge(x1, y1, x2, y2, w, hue, dashed, alpha) {
    const c = this.ctx, dx = x2 - x1, dy = y2 - y1, d = Math.hypot(dx, dy) || 1;
    const mx = (x1 + x2) / 2 + dy / d * 0.07 * d, my = (y1 + y2) / 2 - dx / d * 0.07 * d;
    c.save(); c.globalAlpha = alpha; c.strokeStyle = hue; c.lineWidth = w; c.lineCap = "round";
    if (dashed) c.setLineDash([6, 4]);
    c.beginPath(); c.moveTo(x1, y1); c.quadraticCurveTo(mx, my, x2, y2); c.stroke(); c.restore();
  }

  _hulls() {                                 // m1 soft convex hull per pack (verbatim port)
    const c = this.ctx, packs = {};
    for (const s of this.skills) (packs[s.pack] = packs[s.pack] || []).push([s.x, s.y]);
    for (const pk in packs) {
      const pts = packs[pk];
      if (pts.length < 3) continue;
      const cx = pts.reduce((t, p) => t + p[0], 0) / pts.length;
      const cy = pts.reduce((t, p) => t + p[1], 0) / pts.length;
      const p = [...pts].sort((a, b) => a[0] - b[0] || a[1] - b[1]);
      const cr = (o, a, b) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
      const lo = [], up = [];
      for (const q of p) { while (lo.length > 1 && cr(lo[lo.length - 2], lo[lo.length - 1], q) <= 0) lo.pop(); lo.push(q); }
      for (const q of [...p].reverse()) { while (up.length > 1 && cr(up[up.length - 2], up[up.length - 1], q) <= 0) up.pop(); up.push(q); }
      const hv = lo.slice(0, -1).concat(up.slice(0, -1)).map(([x, y]) => {
        const dx = x - cx, dy = y - cy, d = Math.hypot(dx, dy) || 1;
        return [x + dx / d * 30, y + dy / d * 30];
      });
      const n = hv.length, mid = (a, b) => [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
      c.save(); c.beginPath();
      let m0 = mid(hv[0], hv[1]);
      c.moveTo(m0[0], m0[1]);
      for (let i = 1; i <= n; i++) {
        const v = hv[i % n], m = mid(v, hv[(i + 1) % n]);
        c.quadraticCurveTo(v[0], v[1], m[0], m[1]);
      }
      c.closePath();
      c.globalAlpha = 0.55; c.fillStyle = col("--surface"); c.fill();
      c.globalAlpha = 0.8; c.strokeStyle = col("--border"); c.stroke();
      c.restore();
      const minY = Math.min(...pts.map(q => q[1]));
      this._text(cx, minY - 16, pk.toUpperCase(), 10, col("--text-ghost"));
    }
  }

  _draw(t) {
    const c = this.ctx;
    c.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    c.clearRect(0, 0, this.canvas.width, this.canvas.height);
    c.setTransform(this.dpr * this.scale, 0, 0, this.dpr * this.scale, this.dpr * this.ox, this.dpr * this.oy);
    if (this.ego) return this._drawEgo();
    this._hulls();
    for (const m of this.mainEdges) {        // solid e>0, dashed inferred-only
      const r = this._aR(m.a), d = Math.hypot(m.s.x - m.a.x, m.s.y - m.a.y) || 1;
      const ux = (m.s.x - m.a.x) / d, uy = (m.s.y - m.a.y) / d;
      this._edge(m.a.x + ux * (r + 5), m.a.y + uy * (r + 5), m.s.x - ux * 17, m.s.y - uy * 17,
        1 + 2 * Math.sqrt(m.e + m.i), agentHue(m.a.label), m.e === 0, 0.55);
    }
    for (const s of this.skills) this._drawSkill(s, t);
    for (const A of this.agents) this._drawAgent(A);
  }

  _ellipse(r, alpha) {                       // hop-ring guide, matches the squashed layout
    const c = this.ctx;
    c.save(); c.globalAlpha = alpha; c.strokeStyle = col("--border"); c.lineWidth = 1; c.setLineDash([3, 5]);
    c.beginPath(); c.ellipse(VW / 2, VH / 2, r, r * 0.76, 0, 0, 2 * Math.PI); c.stroke(); c.restore();
  }
  _drawEgo() {
    const c = this.ctx, P = this.ego.placed;
    this._ellipse(132, 0.5);
    this._ellipse(226, 0.35);
    if (this.ego.more1) this._text(VW / 2, VH / 2 - 132 * 0.76 - 12, "+" + this.ego.more1 + " more", 9, col("--text-ghost"));
    if (this.ego.more2) this._text(VW / 2, VH / 2 - 226 * 0.76 - 12, "+" + this.ego.more2 + " more", 9, col("--text-ghost"));
    // label only the governance-chain edges — `used`/`uses` volume would
    // bury the lineage story on hammered-core nodes like run-log
    const labelled = this.ego.edges.filter(e => e.type !== "used" && e.type !== "uses");
    for (const e of this.ego.edges) {
      const a = P.get(e.src), b = P.get(e.dst);
      const w = Math.min(1 + 2 * Math.sqrt((e.weight_e || 0) + (e.weight_i || 0)), 5);
      const hue = e.agent ? agentHue(e.agent) : col("--text-faint");
      this._edge(a.x, a.y, b.x, b.y, w, hue, !(e.weight_e > 0), 0.45);
      if (labelled.length <= 40 && labelled.indexOf(e) !== -1) {
        this._text((a.x + b.x) / 2, (a.y + b.y) / 2, e.type, 8, col("--text-ghost"));
      }
    }
    P.forEach(p => {
      const n = p.n;
      if (n.type === "skill" && this.skillByLabel.has(n.label)) {
        const s = this.skillByLabel.get(n.label);
        const sv = [s.x, s.y]; s.x = p.x; s.y = p.y;
        this._drawSkill(s, 0);
        s.x = sv[0]; s.y = sv[1];
      } else if (n.type === "agent") {
        const A = this.agents.find(x => x.n === n);
        if (A) { const sv = [A.x, A.y]; A.x = p.x; A.y = p.y; this._drawAgent(A); A.x = sv[0]; A.y = sv[1]; }
      } else {
        const hue = col(TYPE_COL[n.type] || "--text-faint");
        c.save();
        c.beginPath(); c.arc(p.x, p.y, 6.5, 0, 2 * Math.PI);
        c.globalAlpha = 0.15; c.fillStyle = hue; c.fill();
        c.globalAlpha = 0.95; c.lineWidth = 1.4; c.strokeStyle = hue; c.stroke();
        c.restore();
        if (this.selected === n) this._ring(p.x, p.y, 12, col("--text-dim"), 1, 0.5);
        const lbl = String(n.label).length > 24 ? String(n.label).slice(0, 23) + "…" : n.label;
        this._text(p.x, p.y + 16, lbl, 9, col("--text-dim"), "mono");
      }
      if (p.hop === 0) this._ring(p.x, p.y, 19, col("--text-dim"), 1.2, 0.6);
    });
  }
}

window.BrainMap = BrainMap;
})();
