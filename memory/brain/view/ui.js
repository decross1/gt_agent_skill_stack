// ui.js — shared chrome for dashboard.html + graph.html: escHTML, date/age
// formatters, severity pills, agent hues, right side-panel overlay, and
// copy-to-clipboard. No fetch(); must work from file:// and http alike.
(function () {
  "use strict";

  const esc = s => String(s == null ? "" : s)
    .replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  // ---- date / age formatters ----
  const fmtDate = iso => String(iso || "").slice(5, 10);                    // 2026-06-09 -> 06-09
  const fmtTs = iso => iso ? iso.slice(0, 10) + " " + iso.slice(11, 16) + "Z" : "";
  function fmtAge(days) {                                                   // 16 -> "16d", 0.45 -> "11h", 0.03 -> "43m"
    if (days == null || isNaN(days)) return "";
    if (days >= 1) return Math.round(days) + "d";
    const h = days * 24;
    if (h >= 1) return Math.round(h) + "h";
    return Math.max(1, Math.round(h * 60)) + "m";
  }
  function fmtBytes(n) {
    if (n == null || isNaN(n)) return "";
    if (n >= 1e6) return (n / 1e6).toFixed(1) + "M";
    if (n >= 1e3) return Math.round(n / 1e3) + "K";
    return n + "B";
  }

  // ---- agent hues: summary-declared first, known ids, then deterministic fallback ----
  const KNOWN_HUE = {
    "nara": "--agent-nara", "coordinator": "--agent-coordinator", "workflow": "--agent-workflow",
    "claude-code-main": "--agent-claude", "nemoclaw_agent": "--agent-nemoclaw"
  };
  const HUE_CYCLE = ["--agent-nara", "--agent-coordinator", "--agent-workflow",
    "--agent-claude", "--agent-nemoclaw", "--agent-other"];
  function agentHue(id) {
    id = String(id == null ? "" : id);
    const fromSummary = ((window.BRAIN_SUMMARY || {}).agents || []).find(a => a.id === id);
    if (fromSummary && fromSummary.hue) return "var(" + fromSummary.hue + ")";
    if (KNOWN_HUE[id]) return "var(" + KNOWN_HUE[id] + ")";
    if (id.indexOf("human:") === 0) return "var(--agent-human)";
    let h = 0;
    for (let k = 0; k < id.length; k++) h = (h * 31 + id.charCodeAt(k)) >>> 0;
    return "var(" + HUE_CYCLE[h % HUE_CYCLE.length] + ")";
  }

  // ---- severity ----
  const SEV_COLOR = { high: "var(--bad)", med: "var(--warn)", low: "var(--idle)" };
  const SEV_CLASS = { high: "bad", med: "warn", low: "idle" };
  const sevColor = s => SEV_COLOR[s] || "var(--text-faint)";
  const sevPill = s => '<span class="ui-pill ' + (SEV_CLASS[s] || "") + '">' + esc(s) + "</span>";

  // ---- small html builders for panel sections ----
  const sec = t => '<div class="ui-sec">' + esc(t) + "</div>";
  const kv = (k, vHtml) => '<div class="ui-kv"><span>' + esc(k) + "</span><span>" + vHtml + "</span></div>";
  const copyBlock = cmd => '<div class="ui-cmd"><code title="' + esc(cmd) + '">' + esc(cmd) +
    '</code><button class="ui-copy" data-copy="' + esc(cmd) + '" title="copy command">copy</button></div>';

  // copy-to-clipboard via delegation; ✓ feedback for 1.1s (m1 idiom, m2 text button)
  document.addEventListener("click", e => {
    const b = e.target.closest && e.target.closest("[data-copy]");
    if (!b) return;
    try {
      const p = navigator.clipboard && navigator.clipboard.writeText(b.getAttribute("data-copy"));
      if (p && p.catch) p.catch(() => {});
    } catch (_) {}
    const old = b.textContent;
    b.textContent = "✓";
    setTimeout(() => { b.textContent = old; }, 1100);
  });

  // ---- shared right side panel (380px overlay; open/Esc/✕ close) ----
  let panelEl = null;
  function ensurePanel() {
    if (panelEl) return panelEl;
    panelEl = document.createElement("aside");
    panelEl.id = "ui-panel";
    panelEl.innerHTML =
      '<div class="ui-panel-head"><span class="ui-panel-title"></span>' +
      '<button class="ui-panel-x" title="close (Esc)">✕</button></div>' +
      '<div class="ui-panel-body"></div>';
    document.body.appendChild(panelEl);
    panelEl.querySelector(".ui-panel-x").addEventListener("click", close);
    document.addEventListener("keydown", e => { if (e.key === "Escape") close(); });
    return panelEl;
  }
  function open(title, sectionsHtml) {
    const p = ensurePanel();
    p.querySelector(".ui-panel-title").textContent = title;
    p.querySelector(".ui-panel-body").innerHTML = sectionsHtml;
    p.querySelector(".ui-panel-body").scrollTop = 0;
    p.classList.add("open");
  }
  function close() { if (panelEl) panelEl.classList.remove("open"); }
  const isOpen = () => !!(panelEl && panelEl.classList.contains("open"));

  // panel + shared-widget styles travel with ui.js so graph.html gets them too
  const css = [
    "#ui-panel{position:fixed;top:0;right:0;bottom:0;width:380px;max-width:100vw;box-sizing:border-box;z-index:40;display:flex;flex-direction:column;",
    "  background:var(--bg);border-left:1px solid var(--border-2);box-shadow:-18px 0 44px rgba(0,0,0,.55);",
    "  transform:translateX(103%);transition:transform .16s ease;font-size:12px}",
    "#ui-panel.open{transform:translateX(0)}",
    "@media (prefers-reduced-motion:reduce){#ui-panel{transition:none}}",
    ".ui-panel-head{display:flex;align-items:center;gap:10px;height:46px;padding:0 14px;border-bottom:1px solid var(--border);flex:none}",
    ".ui-panel-title{font-family:var(--font-mono);font-size:13px;color:var(--text);flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}",
    ".ui-panel-x{all:unset;cursor:pointer;color:var(--text-faint);font-size:13px;padding:2px 7px;border-radius:4px}",
    ".ui-panel-x:hover{color:var(--text);background:var(--surface)}",
    ".ui-panel-body{overflow:auto;padding:12px 14px 18px;display:flex;flex-direction:column;gap:7px}",
    ".ui-sec{font-size:10.5px;text-transform:uppercase;letter-spacing:.08em;color:var(--text-faint);margin-top:9px;display:flex;gap:8px;align-items:center}",
    ".ui-kv{display:flex;gap:10px;align-items:baseline;min-height:21px}",
    ".ui-kv>span:first-child{font-size:11px;color:var(--text-faint);width:98px;flex:none}",
    ".ui-kv>span:last-child{font-family:var(--font-mono);font-size:11.5px;color:var(--text-dim);min-width:0;overflow-wrap:anywhere}",
    ".ui-row{display:flex;align-items:center;gap:8px;min-height:26px}",
    ".ui-id{font-family:var(--font-mono);font-size:11px;color:var(--text-dim);width:118px;flex:none;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}",
    ".ui-bar{flex:1;height:6px;border-radius:3px;background:var(--surface);overflow:hidden;display:flex}",
    ".ui-bar i{display:block;height:100%}",
    ".ui-num{font-family:var(--font-mono);font-size:10px;color:var(--text-faint);flex:none}",
    ".ui-dot{width:8px;height:8px;border-radius:50%;flex:none}",
    ".ui-chip{font-size:10px;font-family:var(--font-mono);padding:1px 8px;border-radius:999px;border:1px solid var(--border-2);color:var(--text-faint)}",
    ".ui-chip.rt{border-color:rgba(16,185,129,.5);color:var(--ok)}",
    ".ui-chip.warn{border-color:rgba(251,191,36,.5);color:var(--warn);background:var(--warn-bg)}",
    ".ui-chip.ok{border-color:rgba(52,211,153,.4);color:var(--ok);background:var(--ok-bg)}",
    ".ui-chip[data-skill]{cursor:pointer}",
    ".ui-pill{font-size:10px;font-family:var(--font-mono);padding:1px 8px;border-radius:999px;line-height:15px;flex:none}",
    ".ui-pill.ok{background:var(--ok-bg);color:var(--ok);border:1px solid rgba(52,211,153,.35)}",
    ".ui-pill.warn{background:var(--warn-bg);color:var(--warn);border:1px solid rgba(251,191,36,.35)}",
    ".ui-pill.bad{background:var(--bad-bg);color:var(--bad);border:1px solid rgba(248,113,113,.35)}",
    ".ui-pill.idle{background:rgba(56,189,248,.08);color:var(--idle);border:1px solid rgba(56,189,248,.3)}",
    ".ui-cmd{display:flex;align-items:center;gap:8px;background:var(--bg);border:1px solid var(--border-2);border-radius:4px;padding:6px 9px;min-width:0}",
    ".ui-cmd code{font-family:var(--font-mono);font-size:11px;color:var(--text-dim);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex:1}",
    ".ui-copy{all:unset;cursor:pointer;font-family:var(--font-mono);font-size:10px;color:var(--text-faint);border:1px solid var(--border-2);border-radius:3px;padding:1px 7px;flex:none}",
    ".ui-copy:hover{color:var(--text);background:var(--surface-2)}",
    ".ui-item{border-top:1px solid var(--border);padding-top:8px;display:flex;flex-direction:column;gap:5px}",
    ".ui-item:first-child{border-top:none;padding-top:0}",
    ".ui-title{font-size:12.5px;color:var(--text)}",
    ".ui-note{font-size:11px;color:var(--text-faint);overflow-wrap:anywhere}",
    ".ui-div{border-top:1px solid var(--border);margin:6px -14px 0}"
  ].join("\n");
  const tag = document.createElement("style");
  tag.textContent = css;
  document.head.appendChild(tag);

  window.UI = {
    esc, escHTML: esc, fmtDate, fmtTs, fmtAge, fmtBytes,
    agentHue, sevColor, sevPill,
    sec, kv, copyBlock,
    panel: { open, close, isOpen }
  };
})();
