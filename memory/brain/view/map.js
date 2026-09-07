// map.js — source-driven Atlas renderer for the Agent System work graph.
// Stable embed contract: BrainMap.mount(canvas, options), instance.update(),
// instance.destroy(), and options.onSelect(node).
// Neighborhoods arrange supplied records; they do not assert causality or ownership.
(function () {
"use strict";

const FULL = { width: 1120, height: 650 };
const COMPACT = { width: 920, height: 430 };
const MAX_VISIBLE = 36;
const NODE_FONT_PX = 17;
const GROUP_FONT_PX = 17;
const MIN_LABEL_CSS_PX = 12;
// The lightest supplied work-link hue still composites above 3:1 on white.
const NORMAL_EDGE_ALPHA = 0.92;
const MODE_EDGE_TYPES = {
  work: new Set(["launched", "uses"]),
  governance: new Set(["about", "targets", "becomes", "produces", "enacts", "extends",
    "references", "authored", "filed", "linked_to"]),
  usage: new Set(["used"]),
};
const MODE_NODE_TYPES = {
  work: new Set(["agent", "spawn", "skill"]),
  governance: new Set(["skill", "proposal", "rule", "harvest_finding", "correction",
    "anomaly", "decision", "agent"]),
  usage: new Set(["agent", "skill"]),
};
const TYPE_LABEL = {
  agent: "actor", spawn: "contract record", skill: "skill", proposal: "proposal",
  rule: "rule", harvest_finding: "finding", correction: "correction",
  anomaly: "anomaly", decision: "decision",
};
const EDGE_LABEL = {
  launched: "recorded launch", uses: "allowed skill", used: "skill attribution",
  about: "about", targets: "targets", becomes: "became", produces: "produced",
  enacts: "enacts", extends: "extends", references: "references", authored: "authored",
  filed: "filed", linked_to: "recorded link",
};
const FALLBACK = {
  "--bg": "#f7f9fc", "--surface": "#ffffff", "--surface-2": "#f2f5f9",
  "--border": "#dfe5ee", "--border-2": "#c7d0dd", "--text": "#1f2937",
  "--text-dim": "#52617a", "--text-faint": "#6f7d91", "--text-ghost": "#8b97a8",
  "--accent": "#5657d8", "--ok": "#2b9ca4", "--warn": "#d88918", "--bad": "#c94b55",
  "--agent-other": "#7c6bd6", "--agent-nara": "#2b9ca4", "--agent-coordinator": "#3d8fb8",
  "--agent-workflow": "#6677cc", "--agent-claude": "#7c6bd6", "--agent-human": "#738196",
  "--agent-nemoclaw": "#9167c9",
};
const COLOR_CACHE = Object.create(null);

function color(name) {
  const match = /^var\((--[a-z0-9-]+)\)$/i.exec(String(name));
  if (match) name = match[1];
  if (!String(name).startsWith("--")) return name;
  if (COLOR_CACHE[name]) return COLOR_CACHE[name];
  let value = "";
  try { value = getComputedStyle(document.documentElement).getPropertyValue(name).trim(); } catch (_) {}
  COLOR_CACHE[name] = value || FALLBACK[name] || "#738196";
  return COLOR_CACHE[name];
}
function clearColorCache() { Object.keys(COLOR_CACHE).forEach(key => delete COLOR_CACHE[key]); }
function text(value) { return String(value == null ? "" : value); }
function lower(value) { return text(value).toLocaleLowerCase(); }
function clamp(value, lo, hi) { return Math.max(lo, Math.min(hi, value)); }
function byRecent(a, b) {
  return text(b.date).localeCompare(text(a.date)) || text(a.label).localeCompare(text(b.label)) ||
    text(a.id).localeCompare(text(b.id));
}
function agentColor(id) {
  if (window.UI && typeof window.UI.agentHue === "function") return color(window.UI.agentHue(id));
  const known = { nara: "--agent-nara", coordinator: "--agent-coordinator", workflow: "--agent-workflow",
    "claude-code-main": "--agent-claude", integrator: "--agent-nemoclaw" };
  if (known[id]) return color(known[id]);
  if (text(id).startsWith("human:")) return color("--agent-human");
  return color("--agent-other");
}
function safeRows(value) { return Array.isArray(value) ? value.filter(row => row && typeof row === "object") : []; }

function injectStyles() {
  if (document.getElementById("bm-style")) return;
  const style = document.createElement("style");
  style.id = "bm-style";
  style.textContent =
    ".bm-hover{position:absolute;display:none;pointer-events:none;z-index:8;box-sizing:border-box;" +
    "width:min(280px,calc(100% - 24px));padding:10px 12px;border:1px solid var(--border);" +
    "border-radius:10px;background:var(--surface);box-shadow:0 14px 34px rgba(15,23,42,.16);" +
    "color:var(--text-dim);font:12px/1.45 system-ui,sans-serif}" +
    ".bm-hover strong{display:block;color:var(--text);font-size:13px;margin-bottom:2px}" +
    ".bm-hover span{display:block;color:var(--text-faint)}" +
    ".bm-back{position:absolute;z-index:7;top:12px;left:12px;padding:7px 10px;border:1px solid var(--border);" +
    "border-radius:8px;background:var(--surface);color:var(--text-dim);font:600 12px system-ui,sans-serif;cursor:pointer}" +
    ".bm-back:hover{color:var(--text);border-color:var(--border-2)}";
  document.head.appendChild(style);
}

class BrainMap {
  static mount(canvas, options) {
    if (canvas.__brainmap && typeof canvas.__brainmap.destroy === "function") canvas.__brainmap.destroy();
    const instance = new BrainMap(canvas, options || {});
    canvas.__brainmap = instance;
    return instance;
  }

  constructor(canvas, options) {
    injectStyles();
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.wrap = canvas.parentElement;
    this.embedded = !!options.embedded;
    this.world = this.embedded ? COMPACT : FULL;
    this.mode = MODE_EDGE_TYPES[options.mode] ? options.mode : (this.embedded ? "usage" : "work");
    this.query = text(options.query).trim();
    this.type = text(options.type || "all");
    this.sum = options.summary || null;
    this.map = options.map || { nodes: [], edges: [], cards: {} };
    this.windowDays = Number.isSafeInteger(options.windowDays) ? options.windowDays : 7;
    this.onSelect = typeof options.onSelect === "function" ? options.onSelect : null;
    this.zoom = 1;
    this.panX = 0;
    this.panY = 0;
    this.selected = null;
    this.hovered = null;
    this.focusId = null;
    this._raf = 0;
    this._destroyed = false;
    this._loop = this._loop.bind(this);
    this._makeDom();
    this._bind();
    this._prepare();
    this.resize();
  }

  _makeDom() {
    if (this.wrap && getComputedStyle(this.wrap).position === "static") this.wrap.style.position = "relative";
    this.hoverCard = document.createElement("div");
    this.hoverCard.className = "bm-hover";
    this.hoverCard.setAttribute("aria-hidden", "true");
    this.wrap.appendChild(this.hoverCard);
    this.back = document.createElement("button");
    this.back.type = "button";
    this.back.className = "bm-back";
    this.back.textContent = "Back to map";
    this.back.style.display = "none";
    this.back.addEventListener("click", () => this.exitEgo());
    this.wrap.appendChild(this.back);
  }

  _bind() {
    this._onMove = event => this._move(event);
    this._onDown = event => this._down(event);
    this._onUp = event => this._up(event);
    this._onLeave = () => { this.hovered = null; this._hideHover(); this._requestDraw(); };
    this._onWheel = event => {
      if (event && typeof event.preventDefault === "function") event.preventDefault();
      this.zoomBy(event.deltaY < 0 ? 0.12 : -0.12);
    };
    this._onResize = () => {
      clearTimeout(this._resizeTimer);
      this._resizeTimer = setTimeout(() => this.resize(), 120);
    };
    this._onVisibility = () => { if (!document.hidden) this._requestDraw(); };
    this._onTheme = () => { clearColorCache(); this._requestDraw(); };
    this.canvas.addEventListener("mousemove", this._onMove);
    this.canvas.addEventListener("mousedown", this._onDown);
    this.canvas.addEventListener("mouseleave", this._onLeave);
    this.canvas.addEventListener("wheel", this._onWheel, { passive: false });
    window.addEventListener("mouseup", this._onUp);
    window.addEventListener("resize", this._onResize);
    window.addEventListener("atlas-theme-change", this._onTheme);
    document.addEventListener("visibilitychange", this._onVisibility);
  }

  destroy() {
    if (this._destroyed) return;
    this._destroyed = true;
    this._stopLoop();
    clearTimeout(this._resizeTimer);
    this.canvas.removeEventListener("mousemove", this._onMove);
    this.canvas.removeEventListener("mousedown", this._onDown);
    this.canvas.removeEventListener("mouseleave", this._onLeave);
    this.canvas.removeEventListener("wheel", this._onWheel);
    window.removeEventListener("mouseup", this._onUp);
    window.removeEventListener("resize", this._onResize);
    window.removeEventListener("atlas-theme-change", this._onTheme);
    document.removeEventListener("visibilitychange", this._onVisibility);
    if (this.hoverCard && typeof this.hoverCard.remove === "function") this.hoverCard.remove();
    if (this.back && typeof this.back.remove === "function") this.back.remove();
    if (this.canvas.__brainmap === this) delete this.canvas.__brainmap;
  }

  update(next) {
    next = next && typeof next === "object" ? next : {};
    if (Object.prototype.hasOwnProperty.call(next, "summary")) this.sum = next.summary;
    if (Object.prototype.hasOwnProperty.call(next, "map")) this.map = next.map || { nodes: [], edges: [], cards: {} };
    if (Number.isSafeInteger(next.windowDays)) this.windowDays = next.windowDays;
    if (MODE_EDGE_TYPES[next.mode]) this.mode = next.mode;
    if (Object.prototype.hasOwnProperty.call(next, "query")) this.query = text(next.query).trim();
    if (Object.prototype.hasOwnProperty.call(next, "type")) this.type = text(next.type || "all");
    if (typeof next.onSelect === "function") this.onSelect = next.onSelect;
    this._prepare();
    this._requestDraw();
    return this;
  }

  setMode(mode) {
    if (!MODE_EDGE_TYPES[mode] || mode === this.mode) return this;
    this.mode = mode;
    this.type = "all";
    this.focusId = null;
    this.back.style.display = "none";
    this.selected = null;
    this._rebuild();
    this.fit();
    return this;
  }

  setFilter(filter) {
    filter = filter || {};
    this.query = text(filter.query).trim();
    this.type = text(filter.type || "all");
    this.focusId = null;
    this.back.style.display = "none";
    this._rebuild();
    this._requestDraw();
    return this;
  }

  _minimumZoom() {
    const scale = Number.isFinite(this.baseScale) && this.baseScale > 0 ? this.baseScale : 1;
    return Math.max(0.72, MIN_LABEL_CSS_PX / NODE_FONT_PX / scale);
  }
  fit() {
    this.zoom = Math.max(1, this._minimumZoom());
    this.panX = 0; this.panY = 0; this._requestDraw(); return this;
  }
  zoomBy(delta) {
    const minimum = this._minimumZoom(), maximum = Math.max(2.1, minimum);
    this.zoom = clamp(this.zoom + delta, minimum, maximum); this._requestDraw(); return this.zoom;
  }
  getZoom() { return this.zoom; }
  getRenderMetrics() {
    const scale = this._renderScale();
    return { labelCssPixels: NODE_FONT_PX * scale,
      groupLabelCssPixels: GROUP_FONT_PX * scale,
      normalEdgeAlpha: NORMAL_EDGE_ALPHA, visibleNodes: this.visible.length };
  }
  getVisibleNodes() { return this.visible.map(item => item.node); }
  getVisibleEdges() { return this.visibleEdges.map(edge => edge.raw); }
  getHiddenCount() { return this.hiddenCount; }
  getMode() { return this.mode; }
  getConnections(id) {
    return this.edges.filter(edge => edge.src === id || edge.dst === id).map(edge => ({
      edge: edge.raw,
      node: this.byId.get(edge.src === id ? edge.dst : edge.src) || null,
      direction: edge.src === id ? "out" : "in",
    })).filter(row => row.node);
  }

  selectById(id, emit) {
    const node = this.byId.get(id);
    if (!node) return false;
    if (!this.visibleById.has(id)) this.egoMode(id, false);
    this.selected = node;
    this._ensureVisible(this.visibleById.get(id));
    this._requestDraw();
    if (emit !== false && this.onSelect) this.onSelect(node);
    return true;
  }

  egoMode(id, emit) {
    if (!this.byId.has(id)) return false;
    this.focusId = id;
    this.back.style.display = "block";
    this._rebuild();
    this.fit();
    return this.selectById(id, emit);
  }

  exitEgo() { this.focusId = null; this.back.style.display = "none"; this._rebuild(); this.fit(); }

  demoCard() {
    const first = this.visible.find(item => item.node.type === "spawn") ||
      this.visible.find(item => item.node.type === "skill") || this.visible[0];
    if (first) this._showHover(first, { clientX: 28, clientY: 42 }, true);
  }

  _prepare() {
    const nodes = safeRows(this.map && this.map.nodes).filter(node => typeof node.id === "string");
    this.nodes = nodes;
    this.byId = new Map(nodes.map(node => [node.id, node]));
    this.cards = this.map && this.map.cards && typeof this.map.cards === "object" ? this.map.cards : {};
    this.edges = safeRows(this.map && this.map.edges).filter(edge =>
      typeof edge.src === "string" && typeof edge.dst === "string" &&
      this.byId.has(edge.src) && this.byId.has(edge.dst)).map(edge => ({
        raw: edge, src: edge.src, dst: edge.dst, type: text(edge.type || "linked_to"),
      }));
    this.skills = nodes.filter(node => node.type === "skill").map(node => ({ n: node, label: node.label }));
    this.agents = nodes.filter(node => node.type === "agent").map(node => ({ n: node, label: node.label }));
    if (this.selected) this.selected = this.byId.get(this.selected.id) || null;
    this.hovered = null;
    this._hideHover();
    if (this.focusId && !this.byId.has(this.focusId)) {
      this.focusId = null;
      this.back.style.display = "none";
    }
    this.asof = ((this.sum && this.sum.window && this.sum.window.newest_event) ||
      (this.map && this.map.generated_at) || "").slice(0, 10);
    this._rebuild();
  }

  _windowUsage(edge) {
    if (edge.type !== "used") return edge.raw;
    const actor = this.byId.get(edge.src), skill = this.byId.get(edge.dst);
    const cells = safeRows(this.sum && this.sum.matrix && this.sum.matrix.cells);
    const cell = cells.find(row => row.agent === (actor && actor.label) && row.skill === (skill && skill.label));
    if (!cell || !cell.by_day || typeof cell.by_day !== "object") return edge.raw;
    let explicit = 0, inferred = 0;
    for (const day of Object.keys(cell.by_day)) {
      const distance = Math.round((Date.parse(this.asof) - Date.parse(day.slice(0, 10))) / 864e5);
      if (distance >= 0 && distance < this.windowDays) {
        explicit += Number(cell.by_day[day].e) || 0;
        inferred += Number(cell.by_day[day].i) || 0;
      }
    }
    return Object.assign({}, edge.raw, { weight_e: explicit, weight_i: inferred });
  }

  _matches(node, query) {
    if (!query) return true;
    const card = this.cards[node.id] || {};
    return [node.id, node.label, node.type, node.pack, node.date, card.title, card.one_line, card.source]
      .map(lower).join(" ").includes(query);
  }

  _rebuild() {
    const allowed = this.nodes.filter(node => MODE_NODE_TYPES[this.mode].has(node.type));
    const modeEdges = this.edges.filter(edge => MODE_EDGE_TYPES[this.mode].has(edge.type));
    const query = lower(this.query);
    let chosen = [];
    if (this.focusId) {
      const ids = new Set([this.focusId]), first = [];
      for (const edge of this.edges) {
        if (edge.src === this.focusId) first.push(edge.dst);
        else if (edge.dst === this.focusId) first.push(edge.src);
      }
      first.sort().slice(0, 18).forEach(id => ids.add(id));
      const second = [];
      const firstHopIds = new Set(ids);
      for (const edge of this.edges) {
        if (firstHopIds.has(edge.src) && !firstHopIds.has(edge.dst)) second.push(edge.dst);
        if (firstHopIds.has(edge.dst) && !firstHopIds.has(edge.src)) second.push(edge.src);
      }
      second.sort().slice(0, MAX_VISIBLE - ids.size).forEach(id => ids.add(id));
      chosen = this.nodes.filter(node => ids.has(node.id));
      this.totalForMode = chosen.length;
      this.hiddenCount = Math.max(0, first.length + second.length + 1 - chosen.length);
    } else if (query) {
      const matches = allowed.filter(node => this._matches(node, query)).sort(byRecent).slice(0, 20);
      const ids = new Set(matches.map(node => node.id));
      const matchedIds = new Set(ids);
      for (const edge of modeEdges) {
        if (ids.size >= MAX_VISIBLE) break;
        if (matchedIds.has(edge.src) && !matchedIds.has(edge.dst)) ids.add(edge.dst);
        else if (matchedIds.has(edge.dst) && !matchedIds.has(edge.src)) ids.add(edge.src);
      }
      chosen = allowed.filter(node => ids.has(node.id));
      this.totalForMode = allowed.filter(node => this._matches(node, query)).length;
      this.hiddenCount = Math.max(0, this.totalForMode - matches.length);
    } else if (this.mode === "work") {
      const recent = allowed.filter(node => node.type === "spawn").sort(byRecent).slice(0, 8);
      const ids = new Set(recent.map(node => node.id));
      const recentIds = new Set(ids);
      for (const edge of modeEdges) {
        if (recentIds.has(edge.src)) ids.add(edge.dst);
        if (recentIds.has(edge.dst)) ids.add(edge.src);
      }
      chosen = allowed.filter(node => ids.has(node.id));
      this.totalForMode = allowed.length;
      this.hiddenCount = Math.max(0, allowed.length - chosen.length);
    } else if (this.mode === "usage") {
      chosen = allowed.slice(0, MAX_VISIBLE);
      this.totalForMode = allowed.length;
      this.hiddenCount = Math.max(0, allowed.length - chosen.length);
    } else {
      const limits = { skill: 18, proposal: 5, harvest_finding: 4, rule: 4,
        correction: 3, anomaly: 1, decision: 1, agent: 2 };
      const buckets = new Map();
      for (const node of allowed) {
        if (!buckets.has(node.type)) buckets.set(node.type, []);
        buckets.get(node.type).push(node);
      }
      for (const [kind, rows] of buckets) chosen.push(...rows.sort(byRecent).slice(0, limits[kind] || 4));
      chosen = chosen.slice(0, MAX_VISIBLE);
      this.totalForMode = allowed.length;
      this.hiddenCount = Math.max(0, allowed.length - chosen.length);
    }
    if (this.type !== "all") chosen = chosen.filter(node => node.type === this.type);
    chosen = chosen.slice(0, MAX_VISIBLE);
    const ids = new Set(chosen.map(node => node.id));
    this.visibleEdges = (this.focusId ? this.edges : modeEdges).filter(edge => ids.has(edge.src) && ids.has(edge.dst))
      .map(edge => ({ raw: this._windowUsage(edge), src: edge.src, dst: edge.dst, type: edge.type }))
      .filter(edge => edge.type !== "used" || (Number(edge.raw.weight_e) || 0) + (Number(edge.raw.weight_i) || 0) > 0);
    this.visible = chosen.map(node => ({ node, x: 0, y: 0, width: 126, height: 42, group: this._group(node) }));
    this.visibleById = new Map(this.visible.map(item => [item.node.id, item]));
    if (this.selected && !this.visibleById.has(this.selected.id)) this.selected = null;
    this._layout();
  }

  _group(node) {
    if (this.focusId) return node.type === "agent" ? "Related actors" :
      node.type === "skill" ? "Related skills" : "Related records";
    if (this.mode === "work") return node.type === "agent" ? "Recorded actors" :
      node.type === "spawn" ? "Recent contract records" : "Allowed skills";
    if (this.mode === "usage") {
      if (node.type === "agent") return "Recorded actors";
      const pack = text(node.pack || "other");
      return pack === "core" ? "Core skills" : pack === "research" ? "Research skills" : "Brain & meta skills";
    }
    if (node.type === "skill") return "Skills";
    if (node.type === "proposal") return "Proposals";
    if (node.type === "harvest_finding") return "Findings";
    if (["rule", "correction", "decision"].includes(node.type)) return "Rules & decisions";
    return "Recorded context";
  }

  _groupTone(name) {
    if (/actor|finding/i.test(name)) return "teal";
    if (/contract|allowed|research/i.test(name)) return "amber";
    return "purple";
  }

  _boundsFor(groups) {
    const W = this.world.width, H = this.world.height;
    const top = this.embedded ? 38 : 50, bottom = this.embedded ? 18 : 32, h = H - top - bottom;
    if (groups.length === 1) return [{ x: 24, y: top, width: W - 48, height: h }];
    if (groups.length === 2) return [{ x: 24, y: top, width: W * .43, height: h },
      { x: W * .47, y: top, width: W * .51, height: h }];
    if (groups.length === 3) return [{ x: 20, y: top, width: W * .19, height: h },
      { x: W * .225, y: top, width: W * .49, height: h },
      { x: W * .73, y: top, width: W * .25, height: h }];
    const left = { x: 20, y: top, width: W * .34, height: h };
    const rightX = W * .375, rightW = W * .605, gap = 14;
    const cellW = (rightW - gap) / 2, cellH = (h - gap) / 2;
    const out = [left];
    for (let index = 1; index < groups.length; index++) {
      const cell = index - 1;
      out.push({ x: rightX + (cell % 2) * (cellW + gap), y: top + Math.floor(cell / 2) * (cellH + gap),
        width: cellW, height: cellH });
    }
    return out;
  }

  _layout() {
    const order = [];
    for (const item of this.visible) if (!order.includes(item.group)) order.push(item.group);
    const bounds = this._boundsFor(order);
    this.groups = order.map((name, index) => ({ name, tone: this._groupTone(name), bounds: bounds[index] }));
    for (const group of this.groups) {
      const items = this.visible.filter(item => item.group === group.name), b = group.bounds;
      const gapX = 10, gapY = 9, innerX = 14, innerTop = 42, innerBottom = 14;
      const maxCols = Math.max(1, Math.floor((b.width - innerX * 2 + gapX) / (116 + gapX)));
      const availableH = Math.max(44, b.height - innerTop - innerBottom);
      let cols = maxCols;
      while (cols > 1 && Math.ceil(items.length / (cols - 1)) * 50 <= availableH) cols--;
      const rows = Math.max(1, Math.ceil(items.length / cols));
      const nodeW = clamp((b.width - innerX * 2 - gapX * (cols - 1)) / cols, 88, 144);
      const rowStep = Math.min(52, availableH / rows), nodeH = clamp(rowStep - gapY, 31, 42);
      items.forEach((item, index) => {
        const column = index % cols, row = Math.floor(index / cols);
        item.width = nodeW; item.height = nodeH;
        item.x = b.x + innerX + column * (nodeW + gapX) + nodeW / 2;
        item.y = b.y + innerTop + row * rowStep + nodeH / 2;
      });
    }
  }

  resize() {
    if (this._destroyed) return;
    const dpr = window.devicePixelRatio || 1;
    const width = this.canvas.clientWidth || (this.wrap && this.wrap.clientWidth) || this.world.width;
    const height = this.canvas.clientHeight || (this.wrap && this.wrap.clientHeight) || this.world.height;
    this.canvas.width = Math.max(1, Math.round(width * dpr));
    this.canvas.height = Math.max(1, Math.round(height * dpr));
    this.cssWidth = width; this.cssHeight = height; this.dpr = dpr;
    this.baseScale = Math.min(width / this.world.width, height / this.world.height);
    this.zoom = Math.max(this.zoom, this._minimumZoom());
    this._requestDraw();
  }

  _renderScale() {
    return Math.max(this.baseScale * this.zoom, MIN_LABEL_CSS_PX / NODE_FONT_PX);
  }
  _transform() {
    const scale = this._renderScale();
    return { scale, x: (this.cssWidth - this.world.width * scale) / 2 + this.panX,
      y: (this.cssHeight - this.world.height * scale) / 2 + this.panY };
  }

  _ensureVisible(item) {
    if (!item || !this.cssWidth || !this.cssHeight) return;
    const transform = this._transform(), margin = 12;
    const left = transform.x + (item.x - item.width / 2) * transform.scale;
    const right = transform.x + (item.x + item.width / 2) * transform.scale;
    const top = transform.y + (item.y - item.height / 2) * transform.scale;
    const bottom = transform.y + (item.y + item.height / 2) * transform.scale;
    if (left < margin) this.panX += margin - left;
    else if (right > this.cssWidth - margin) this.panX += this.cssWidth - margin - right;
    if (top < margin) this.panY += margin - top;
    else if (bottom > this.cssHeight - margin) this.panY += this.cssHeight - margin - bottom;
  }

  _worldPoint(event) {
    const rect = this.canvas.getBoundingClientRect(), transform = this._transform();
    return { x: (event.clientX - rect.left - transform.x) / transform.scale,
      y: (event.clientY - rect.top - transform.y) / transform.scale };
  }
  _pick(point) {
    for (let index = this.visible.length - 1; index >= 0; index--) {
      const item = this.visible[index];
      if (Math.abs(point.x - item.x) <= item.width / 2 && Math.abs(point.y - item.y) <= item.height / 2) return item;
    }
    return null;
  }
  _move(event) {
    if (this.drag) {
      const dx = event.clientX - this.drag.clientX, dy = event.clientY - this.drag.clientY;
      if (Math.abs(dx) + Math.abs(dy) > 3) this.drag.moved = true;
      this.panX = this.drag.panX + dx; this.panY = this.drag.panY + dy;
      this._hideHover(); this._requestDraw(); return;
    }
    const hit = this._pick(this._worldPoint(event));
    this.hovered = hit; this.canvas.style.cursor = hit ? "pointer" : "grab";
    if (hit) this._showHover(hit, event); else this._hideHover();
    this._requestDraw();
  }
  _down(event) {
    const hit = this._pick(this._worldPoint(event));
    this.downHit = hit;
    if (!hit) this.drag = { clientX: event.clientX, clientY: event.clientY,
      panX: this.panX, panY: this.panY, moved: false };
  }
  _up(event) {
    if (this.downHit) {
      const hit = this._pick(this._worldPoint(event));
      if (hit && hit.node.id === this.downHit.node.id) this.selectById(hit.node.id);
    }
    this.downHit = null; this.drag = null; this.canvas.style.cursor = "grab";
  }

  _showHover(item, event, fixed) {
    const node = item.node, card = this.cards[node.id] || {};
    this.hoverCard.textContent = "";
    const strong = document.createElement("strong"); strong.textContent = text(card.title || node.label || node.id);
    const meta = document.createElement("span");
    meta.textContent = [TYPE_LABEL[node.type] || node.type, node.date || "date unavailable"].join(" · ");
    this.hoverCard.appendChild(strong); this.hoverCard.appendChild(meta); this.hoverCard.style.display = "block";
    const bounds = this.wrap.getBoundingClientRect();
    const x = fixed ? 24 : event.clientX - bounds.left + 14, y = fixed ? 40 : event.clientY - bounds.top + 14;
    this.hoverCard.style.left = clamp(x, 12, Math.max(12, bounds.width - 292)) + "px";
    this.hoverCard.style.top = clamp(y, 12, Math.max(12, bounds.height - 92)) + "px";
  }
  _hideHover() { this.hoverCard.style.display = "none"; }
  _requestDraw() { if (!this._raf && !this._destroyed && !document.hidden) this._raf = requestAnimationFrame(this._loop); }
  _stopLoop() { if (this._raf) cancelAnimationFrame(this._raf); this._raf = 0; }
  _loop() { this._raf = 0; if (!this._destroyed && !document.hidden) this._draw(); }

  _roundRect(ctx, x, y, width, height, radius) {
    const r = Math.min(radius, width / 2, height / 2);
    ctx.beginPath(); ctx.moveTo(x + r, y); ctx.lineTo(x + width - r, y);
    ctx.quadraticCurveTo(x + width, y, x + width, y + r); ctx.lineTo(x + width, y + height - r);
    ctx.quadraticCurveTo(x + width, y + height, x + width - r, y + height); ctx.lineTo(x + r, y + height);
    ctx.quadraticCurveTo(x, y + height, x, y + height - r); ctx.lineTo(x, y + r);
    ctx.quadraticCurveTo(x, y, x + r, y); ctx.closePath();
  }

  _tone(tone) {
    const root = document.documentElement;
    const dark = !!root && root.getAttribute("data-theme") === "dark";
    const palettes = dark ? {
      teal: ["rgba(43,156,164,.10)", "rgba(78,188,193,.35)", "#4ebcc1"],
      amber: ["rgba(216,137,24,.10)", "rgba(224,164,73,.36)", "#e0a449"],
      purple: ["rgba(86,87,216,.11)", "rgba(129,130,232,.38)", "#9293ed"],
    } : {
      teal: ["rgba(43,156,164,.075)", "rgba(43,156,164,.24)", "#238b92"],
      amber: ["rgba(216,137,24,.07)", "rgba(216,137,24,.24)", "#c27a10"],
      purple: ["rgba(86,87,216,.07)", "rgba(86,87,216,.23)", "#5657d8"],
    };
    return palettes[tone] || palettes.purple;
  }

  _drawGroup(group) {
    const ctx = this.ctx, b = group.bounds, tone = this._tone(group.tone);
    ctx.save(); this._roundRect(ctx, b.x, b.y, b.width, b.height, 30);
    ctx.fillStyle = tone[0]; ctx.fill(); ctx.strokeStyle = tone[1]; ctx.lineWidth = 1; ctx.stroke();
    ctx.fillStyle = tone[2]; ctx.font = "600 " + GROUP_FONT_PX + "px system-ui,sans-serif";
    ctx.textAlign = "left"; ctx.textBaseline = "middle";
    const count = this.visible.filter(item => item.group === group.name).length;
    ctx.fillText(group.name + " · " + count, b.x + 16, b.y + 21); ctx.restore();
  }

  _drawEdge(edge) {
    const from = this.visibleById.get(edge.src), to = this.visibleById.get(edge.dst);
    if (!from || !to) return;
    const ctx = this.ctx, explicit = Number(edge.raw.weight_e) || 0, inferred = Number(edge.raw.weight_i) || 0;
    const root = document.documentElement, dark = !!root && root.getAttribute("data-theme") === "dark";
    let stroke = dark ? color("--text-faint") : "#52617a", dashed = false;
    if (edge.type === "uses") { stroke = this._tone("amber")[2]; dashed = true; }
    else if (edge.type === "launched") stroke = this._tone("teal")[2];
    else if (edge.type === "used") {
      const actor = (this.byId.get(edge.src) || {}).label;
      if (dark) stroke = agentColor(actor);
      else {
        const palette = ["#4f5fb8", "#6b479d", "#176c73", "#8a5200"];
        let hash = 0; for (const char of text(actor)) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
        stroke = palette[hash % palette.length];
      }
      dashed = !explicit && !!inferred;
    } else if (["about", "targets", "enacts", "extends", "becomes", "produces"].includes(edge.type)) {
      stroke = this._tone("purple")[2];
    }
    const selected = this.selected && (edge.src === this.selected.id || edge.dst === this.selected.id);
    ctx.save(); ctx.strokeStyle = stroke; ctx.globalAlpha = selected ? 1 : NORMAL_EDGE_ALPHA;
    ctx.lineWidth = selected ? 1.8 : 1;
    if (dashed) ctx.setLineDash(edge.type === "uses" ? [5, 5] : [2, 5]);
    const mx = (from.x + to.x) / 2, bend = (to.y - from.y) * .08;
    ctx.beginPath(); ctx.moveTo(from.x, from.y);
    ctx.quadraticCurveTo(mx, (from.y + to.y) / 2 - bend, to.x, to.y); ctx.stroke(); ctx.restore();
  }

  _selectedRelationLabel() {
    if (!this.selected) return "";
    const counts = new Map();
    for (const edge of this.visibleEdges) {
      if (edge.src !== this.selected.id && edge.dst !== this.selected.id) continue;
      counts.set(edge.type, (counts.get(edge.type) || 0) + 1);
    }
    const rows = [...counts].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
    if (!rows.length) return "";
    const first = rows[0], label = (first[1] > 1 ? first[1] + " × " : "") +
      (EDGE_LABEL[first[0]] || first[0]);
    return rows.length > 1 ? label + " · +" + (rows.length - 1) + " relation type" +
      (rows.length === 2 ? "" : "s") + " in inspector" : label;
  }

  _drawSelectedRelationLabel() {
    const raw = this._selectedRelationLabel();
    if (!raw || !this.cssWidth || !this.cssHeight) return;
    const ctx = this.ctx, maxWidth = Math.max(120, this.cssWidth - 24);
    const width = Math.min(maxWidth, Math.max(140, raw.length * 7 + 22));
    const cap = Math.max(10, Math.floor((width - 22) / 7));
    const label = raw.length > cap ? raw.slice(0, Math.max(1, cap - 1)) + "…" : raw;
    const x = 12, y = Math.max(12, this.cssHeight - 46);
    ctx.save(); ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    this._roundRect(ctx, x, y, width, 34, 8);
    ctx.fillStyle = color("--surface"); ctx.fill();
    ctx.strokeStyle = color("--border-2"); ctx.lineWidth = 1; ctx.stroke();
    ctx.fillStyle = color("--text"); ctx.font = "600 12px system-ui,sans-serif";
    ctx.textAlign = "left"; ctx.textBaseline = "middle"; ctx.fillText(label, x + 11, y + 17);
    ctx.restore();
  }

  _labelLines(label, width) {
    const cap = Math.max(8, Math.floor(width / 9.2));
    const raw = text(label || "Untitled record").replace(/\s+/g, " ").trim();
    if (raw.length <= cap) return [raw];
    const words = raw.split(" "), lines = [""];
    for (const word of words) {
      const current = lines[lines.length - 1];
      if ((current + " " + word).trim().length <= cap) lines[lines.length - 1] = (current + " " + word).trim();
      else if (lines.length === 1) lines.push(word);
      else { lines[1] = (lines[1] + " " + word).trim(); break; }
    }
    if (lines[1] && lines[1].length > cap) lines[1] = lines[1].slice(0, Math.max(1, cap - 1)) + "…";
    else if (raw.length > lines.join(" ").length) lines[lines.length - 1] = lines[lines.length - 1].slice(0, Math.max(1, cap - 1)) + "…";
    return lines;
  }

  _drawNode(item) {
    const ctx = this.ctx, node = item.node, selected = this.selected === node, hovered = this.hovered === item;
    const tone = this._tone(this._groupTone(item.group));
    ctx.save(); this._roundRect(ctx, item.x - item.width / 2, item.y - item.height / 2, item.width, item.height, 10);
    ctx.fillStyle = color("--surface"); ctx.fill();
    ctx.strokeStyle = selected ? color("--accent") : hovered ? tone[2] : color("--border-2");
    ctx.lineWidth = selected ? 2.4 : hovered ? 1.6 : 1; ctx.stroke();
    ctx.beginPath(); ctx.arc(item.x - item.width / 2 + 11, item.y, 3.5, 0, Math.PI * 2);
    ctx.fillStyle = node.type === "agent" ? agentColor(node.label) : tone[2]; ctx.fill();
    const lines = this._labelLines(node.label || node.id, item.width - 28);
    ctx.fillStyle = color("--text"); ctx.font = "600 " + NODE_FONT_PX + "px system-ui,sans-serif";
    ctx.textAlign = "left"; ctx.textBaseline = "middle";
    const start = item.y - (lines.length - 1) * 7;
    lines.forEach((line, index) => ctx.fillText(line, item.x - item.width / 2 + 20, start + index * 18));
    ctx.restore();
  }

  _draw() {
    const ctx = this.ctx;
    ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0); ctx.clearRect(0, 0, this.cssWidth, this.cssHeight);
    const transform = this._transform();
    ctx.setTransform(this.dpr * transform.scale, 0, 0, this.dpr * transform.scale,
      this.dpr * transform.x, this.dpr * transform.y);
    for (const group of this.groups) this._drawGroup(group);
    for (const edge of this.visibleEdges) this._drawEdge(edge);
    for (const item of this.visible) this._drawNode(item);
    if (!this.visible.length) {
      ctx.save(); ctx.fillStyle = color("--text-faint"); ctx.font = "500 14px system-ui,sans-serif";
      ctx.textAlign = "center"; ctx.textBaseline = "middle";
      ctx.fillText("No recorded nodes match this view.", this.world.width / 2, this.world.height / 2); ctx.restore();
    }
    this._drawSelectedRelationLabel();
  }
}

window.BrainMap = BrainMap;
})();
