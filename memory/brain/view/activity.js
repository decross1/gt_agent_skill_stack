// Read-only view of one supplied summary. No actor authentication or ledger writes.
(function (root) {
  "use strict";
  const object = value => value && typeof value === "object" && !Array.isArray(value);
  const text = value => typeof value === "string" ? value : value == null ? "Unknown" : JSON.stringify(value);
  const rows = value => Array.isArray(value) ? value : [];
  const count = value => Number.isInteger(value) && value >= 0 ? String(value) : "Unknown";
  const known = value => typeof value === "string" && value.trim() ? value : "Unknown";
  const proposalHref = value => typeof value === "string" && /^P-[0-9]+$/.test(value)
    ? "proposal_review.html?id=" + encodeURIComponent(value) : null;

  function validSummary(data) {
    return !!(object(data) && data.schema_version === 2 && object(data.window) &&
      Array.isArray(data.agents) && Array.isArray(data.skills) && Array.isArray(data.timeline) &&
      Array.isArray(data.inbox) && object(data.matrix) && Array.isArray(data.matrix.cells) &&
      object(data.loop) && Array.isArray(data.loop.chains));
  }

  function attentionItems(data) {
    const keys = ["framework_actions", "external_acknowledgements", "backlog_history"];
    const invalidRows = values => values.filter(value => !object(value)).length;
    if (!Object.prototype.hasOwnProperty.call(data, "attention")) return {
      note: "Legacy inbox projection · view-only; governed attention partitions unavailable",
      malformed: invalidRows(data.inbox), error: "", items: data.inbox.filter(object).map(item =>
        ({...item, actionable: false, action_cmd: null, attentionGroup: "legacy inbox"}))};
    const canonical = object(data.attention) && keys.every(key => Array.isArray(data.attention[key]));
    if (!canonical) return {note: "Attention unavailable: supplied partitions are malformed; raw inbox not used",
      malformed: 0, error: "Malformed attention partitions could not be displayed; this view is incomplete.", items: []};
    return {note: "Supplied attention partitions; external acknowledgements are view-only",
      malformed: keys.reduce((sum, key) => sum + invalidRows(data.attention[key]), 0), error: "",
      items: keys.flatMap(key => data.attention[key].filter(object).map(item => {
        const viewOnly = key !== "framework_actions" || item.surface !== "framework";
        return {...item, attentionGroup: key.replaceAll("_", " "),
          ...(viewOnly ? {actionable: false, action_cmd: null} : {})};
      }))};
  }

  // Calendar qualification, not a clock, future-date policy or execution receipt.
  function recordedTime(value, requireZone) {
    if (typeof value !== "string") return null;
    const match = /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}):(\d{2})(?:\.\d+)?(Z|[+-]\d{2}:\d{2})?)?$/.exec(value);
    if (!match || (requireZone && !match[7])) return null;
    const [year, month, day] = match.slice(1, 4).map(Number);
    const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
    const days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
    if (year < 1 || month < 1 || month > 12 || day < 1 || day > days[month - 1]) return null;
    if (match[4] && (Number(match[4]) > 23 || Number(match[5]) > 59 || Number(match[6]) > 59)) return null;
    if (match[7] && match[7] !== "Z" && (Number(match[7].slice(1, 3)) > 23 || Number(match[7].slice(4)) > 59)) return null;
    return value;
  }

  async function digest(runtime, value) {
    if (!runtime.crypto || !runtime.crypto.subtle || !runtime.TextEncoder) return null;
    try {
      const bytes = new runtime.TextEncoder().encode(value);
      const hash = await runtime.crypto.subtle.digest("SHA-256", bytes);
      return Array.from(new Uint8Array(hash), byte => byte.toString(16).padStart(2, "0")).join("");
    } catch (_) { return null; }
  }

  function createStore(runtime, snapshot, changed) {
    const data = validSummary(snapshot) ? snapshot : null;
    const state = {data, source: data ? "snapshot" : "missing", receivedAt: null,
      checkedAt: null, error: !data ? snapshot == null ? "Snapshot unavailable: missing or failed to load/parse." : "The supplied snapshot is unsupported or incomplete." : "",
      loading: false, hash: null, hashKind: data ? "snapshot JSON value" : null};
    let revision = 0, controller = null, disposed = false;
    if (data) digest(runtime, JSON.stringify(data)).then(hash => {
      if (!disposed && state.data === data && state.source === "snapshot") { state.hash = hash; changed(state); }
    });
    state.refresh = async function () {
      if (disposed) return false;
      if (!/^https?:$/.test(runtime.location.protocol)) {
        state.error = "File snapshot: network refresh is unavailable.";
        changed(state); return false;
      }
      const current = ++revision;
      if (controller) controller.abort();
      controller = runtime.AbortController ? new runtime.AbortController() : null;
      const ownController = controller;
      state.loading = true; changed(state);
      let timer;
      try {
        const request = (async () => {
          const response = await runtime.fetch("api/summary", {cache: "no-store", redirect: "error", signal: ownController ? ownController.signal : undefined});
          if (response.redirected) throw new Error("Unexpected summary redirect rejected");
          if (!response.ok) throw new Error("HTTP " + response.status);
          const body = await response.text();
          const parsed = JSON.parse(body);
          if (!validSummary(parsed)) throw new Error("Unsupported or incomplete summary response");
          return {data: parsed, hash: await digest(runtime, body)};
        })();
        const timeout = new Promise((_, reject) => {
          timer = runtime.setTimeout(() => { if (ownController) ownController.abort(); reject(new Error("Request timed out after 5 seconds")); }, 5000);
        });
        const result = await Promise.race([request, timeout]);
        if (current !== revision || disposed) return false;
        state.data = result.data; state.hash = result.hash; state.hashKind = "response bytes";
        state.source = "response"; state.receivedAt = new runtime.Date().toISOString(); state.error = "";
        return true;
      } catch (error) {
        if (current === revision && !disposed) state.error = error instanceof Error ? error.message : "Request or JSON response failed";
        return false;
      } finally {
        runtime.clearTimeout(timer);
        if (current === revision && !disposed) {
          state.loading = false; state.checkedAt = new runtime.Date().toISOString(); changed(state);
        }
      }
    };
    state.dispose = function () { disposed = true; revision++; if (controller) controller.abort(); };
    return state;
  }

  function lifecycle(chain) {
    const healing = object(chain.healing) ? chain.healing : {};
    const accepted = object(healing.accepted) ? healing.accepted : {};
    const enacted = object(healing.enacted) ? healing.enacted : {};
    const verified = object(healing.verified) ? healing.verified : {};
    const evidence = object(enacted.evidence) ? enacted.evidence : {};
    const targetPath = chain.target_type === "skill" && typeof chain.target === "string" && /^[a-z0-9-]+$/.test(chain.target)
      ? ".agents/skills/" + chain.target + "/SKILL.md" : null;
    const completeEnactment = enacted.state === "enacted" && typeof evidence.commit === "string" && /^[0-9a-f]{40}$/i.test(evidence.commit) &&
      Array.isArray(evidence.paths) && evidence.paths.length > 0 && evidence.paths.every(path =>
        typeof path === "string" && path.trim() && !path.startsWith("/") && !path.split("/").includes("..")) &&
      (chain.target_type !== "skill" || (targetPath !== null && evidence.paths.includes(targetPath)));
    const rejected = ["rejected", "auto-reject"].includes(chain.final_verdict) || chain.lane === "rejected";
    const acceptedVerdict = ["accepted", "auto-accept"].includes(chain.final_verdict);
    const contradiction = (accepted.state === "accepted" && !acceptedVerdict) ||
      (!acceptedVerdict && enacted.state === "enacted") || (acceptedVerdict && accepted.state !== "accepted");
    let next = "Owner: review the recorded proposal and its supporting evidence.";
    if (chain.lane === "draft") next = "A separately governed graduation record is required before Review can decide this draft.";
    else if (rejected) next = "Owner: retain the rejection and its reason; any new proposal needs a separate review.";
    else if (enacted.state === "enacted" && !completeEnactment) next = "Owner: provide the implementation commit and paths in the canonical enactment evidence before assessing verification.";
    else if (accepted.state === "accepted" && enacted.state !== "enacted") next = "Owner: provide a reviewed implementation commit and matching changed paths.";
    else if (completeEnactment) next = "Owner: independently verify execution and results against this implementation; a reported pass is insufficient.";
    if (contradiction) next = "Owner: reconcile the contradictory verdict and lifecycle projection against the original records.";
    let stage = "Supplied lane · " + known(chain.lane);
    if (contradiction) stage = "Lifecycle contradiction needs reconciliation";
    else if (rejected) stage = "Rejected record";
    else if (completeEnactment) stage = "Implementation receipt supplied; outcome still unverified";
    else if (enacted.state === "enacted") stage = "Enactment claim lacks a complete receipt";
    else if (accepted.state === "accepted") stage = "Recorded accepted; implementation evidence needed";
    else if (chain.lane === "draft") stage = "Draft held; graduation closed";
    else if (["open", "human-review"].includes(chain.lane)) stage = "Awaiting governed Review";
    return {
      verdict: known(chain.final_verdict), lane: known(chain.lane),
      acceptance: rejected ? "Rejected verdict" : accepted.state === "accepted" ? "Recorded acceptance" : "Acceptance unknown / pending",
      enactment: completeEnactment ? "Projector-reported Git/path evidence" : enacted.state === "enacted" ? "Incomplete enactment claim; evidence unavailable" : "Enactment " + known(enacted.state).toLowerCase(),
      // This page has no independent execution verifier, even for a supplied label.
      verification: object(verified.reported) ? "Reported verification · pending" : "Independent verification not established",
      acceptedAt: recordedTime(accepted.at), enactedAt: recordedTime(enacted.at),
      reportedAt: object(verified.reported) ? recordedTime(verified.reported.at) : null,
      contradiction, next, stage, healing, completeEnactment, evidence
    };
  }

  function lifecycleCounts(value) {
    const supplied = rows(value), readable = supplied.filter(object);
    const views = readable.map(chain => ({chain, view: lifecycle(chain)}));
    return {
      readable: readable.length,
      malformed: supplied.length - readable.length,
      accepted: readable.filter(chain => object(chain.healing) && object(chain.healing.accepted) && chain.healing.accepted.state === "accepted").length,
      enacted: readable.filter(chain => object(chain.healing) && object(chain.healing.enacted) && chain.healing.enacted.state === "enacted").length,
      completeReceipts: views.filter(item => item.view.completeEnactment).length,
      reportedVerification: readable.filter(chain => object(chain.healing) && object(chain.healing.verified) && object(chain.healing.verified.reported)).length,
      contradictions: views.filter(item => item.view.contradiction).length
    };
  }

  function mount(runtime, document) {
    const expandedEvidence = new Set();
    const pageSize = 12;
    const pages = new Map();
    let activePanel = "activity";
    let lastRenderKey;
    const get = id => document.getElementById(id);
    const el = (tag, content, className) => {
      const node = document.createElement(tag);
      if (content !== undefined) node.textContent = text(content);
      if (className) node.className = className;
      return node;
    };
    const add = (node, ...children) => { children.forEach(child => node.appendChild(child)); return node; };
    const clear = node => node.replaceChildren();
    const empty = (host, message) => host.appendChild(el("p", message, "empty"));
    const source = (host, value) => host.appendChild(el("p", "Source: " + value, "source-ref"));
    const details = (host, label, value, key) => {
      const node = el("details");
      node.dataset.evidenceKey = key; node.open = expandedEvidence.has(key);
      add(node, el("summary", label), el("p", value, "source-ref")); host.appendChild(node);
    };
    const pair = (host, key, value) => add(host, el("dt", key), el("dd", value));
    const compactTitle = value => { const full = known(value); return full.length > 72 ? full.slice(0, 71).trimEnd() + "…" : full; };
    const inspectLink = proposalId => {
      const href = proposalHref(proposalId);
      if (!href) return null;
      const link = el("a", "Inspect record", "inspect-link");
      link.setAttribute("href", href);
      link.setAttribute("aria-label", "Inspect record " + proposalId + " in Review");
      return link;
    };
    const table = (host, headings, caption) => {
      const wrap = el("div", undefined, "table-scroll"), grid = el("table"), head = el("thead"), tr = el("tr"), body = el("tbody");
      headings.forEach(label => { const th = el("th", label); th.setAttribute("scope", "col"); tr.appendChild(th); });
      add(head, tr); add(grid, el("caption", caption), head, body); add(wrap, grid); host.appendChild(wrap); return body;
    };
    const tr = (host, values) => { const row = el("tr"); values.forEach(value => row.appendChild(value && value.tagName ? value : el("td", value))); host.appendChild(row); };
    const page = (host, key, values, renderValues) => {
      const last = Math.max(0, Math.ceil(values.length / pageSize) - 1);
      const current = Math.min(Math.max(pages.get(key) || 0, 0), last);
      pages.set(key, current);
      renderValues(values.slice(current * pageSize, (current + 1) * pageSize));
      if (values.length <= pageSize) return;
      const controls = el("div", undefined, "pager");
      const previous = el("button", "Previous"); previous.setAttribute("type", "button"); previous.disabled = current === 0;
      const next = el("button", "Next"); next.setAttribute("type", "button"); next.disabled = current === last;
      previous.addEventListener("click", () => { pages.set(key, current - 1); render(store); });
      next.addEventListener("click", () => { pages.set(key, current + 1); render(store); });
      add(controls, previous, el("p", "Showing " + (current * pageSize + 1) + "–" + Math.min(values.length, (current + 1) * pageSize) + " of " + values.length), next);
      host.appendChild(controls);
    };
    const resetPages = () => pages.clear();
    let store;
    const stateLabel = state => !state.data ? "Data unavailable" : state.source === "snapshot" ? "Snapshot data" : state.error ? "Cached response · refresh failed" : "Live response received";
    function showSource(state, malformed, attentionError) {
      const label = stateLabel(state);
      get("data-state").textContent = label + (state.loading ? " · checking for an update…" : "");
      const warning = (state.error || "") + (malformed ? " " + malformed + " malformed rows could not be displayed; this view is incomplete." : "") + (attentionError ? " " + attentionError : "");
      const notice = (state.loading ? "Checking for a summary update" : label + (state.checkedAt ? "; checked " + state.checkedAt : "")) + (warning ? ". " + warning : "");
      if (get("data-announcement").textContent !== notice) get("data-announcement").textContent = notice;
      get("data-warning").textContent = warning;
      get("refresh-data").disabled = state.loading || !/^https?:$/.test(runtime.location.protocol);
      const host = get("source-metadata"); clear(host);
      const d = state.data;
      pair(host, "Loaded from", state.source === "response" ? "api/summary (requested on this origin; redirects rejected)" : state.data ? "summary_data.js (supplied snapshot)" : "No valid summary loaded");
      pair(host, "Generated at", d ? recordedTime(d.generated_at, true) || "Unknown or invalid generation timestamp" : "Unknown");
      pair(host, "Last received", state.receivedAt || "No successful response in this page session");
      pair(host, "Last checked", state.checkedAt || "No network check completed");
      pair(host, "Newest recorded date", d ? recordedTime(d.window.newest_event) || "Unknown" : "Unknown");
      pair(host, "Payload SHA256", state.hash ? state.hash + " (" + state.hashKind + ")" : "Unavailable; payload identity not established");
      pair(host, "Source repository label", d ? known(d.repo) + " (reported)" : "Unknown");
      pair(host, "Source revision / cursor", "Not supplied. The payload hash does not identify a Git revision or an exact source-ledger prefix.");
      pair(host, "Trust", "Recorded labels do not authenticate people or agents. Historical references do not establish an active session. A fresh response does not prove fresh underlying events or verified execution.");
    }

    function showLifecycleOverview(values) {
      const host = get("lifecycle-overview");
      if (!host) return; // The previous HTML shell has no optional overview.
      const stats = lifecycleCounts(values), unknownAcceptance = stats.readable - stats.accepted;
      const unknownEnactment = stats.readable - stats.enacted, unknownVerification = stats.readable - stats.reportedVerification;
      if (!stats.readable) {
        add(host, el("p", "No readable supplied records · " + stats.malformed + " malformed. Lifecycle counts are unknown.", "overview-total"),
          el("p", "No supplied record is treated as a healthy zero or evidence of absence.", "source-note"));
        return;
      }
      add(host, el("p", stats.readable + " readable supplied records · " + stats.malformed + " malformed", "overview-total"));
      const grid = el("dl", undefined, "stage-overview");
      const stat = (label, value) => add(grid, add(el("div", undefined, "stage-stat"), el("dt", label), el("dd", value)));
      stat("Acceptance states", stats.accepted + " recorded acceptance" + (stats.accepted === 1 ? "" : "s") + " · " + unknownAcceptance + " unknown, pending, rejected, or other");
      stat("Enactment states", stats.enacted + " recorded enactment claim" + (stats.enacted === 1 ? "" : "s") + " · " + stats.completeReceipts + " structurally complete reported Git/path receipt" + (stats.completeReceipts === 1 ? "" : "s") + " · " + unknownEnactment + " unknown, pending, rejected, or other");
      stat("Verification evidence", stats.reportedVerification + " reported verification record" + (stats.reportedVerification === 1 ? "" : "s") + " · " + unknownVerification + " unknown or absent");
      stat("Contradictions", stats.contradictions ? stats.contradictions + " readable record" + (stats.contradictions === 1 ? "" : "s") + " need reconciliation" : "None observed in readable records; malformed records remain unknown");
      add(host, grid, el("p", "Counts can overlap and describe supplied states only. They do not show throughput, causal flow, runtime liveness or independently verified outcomes.", "source-note"));
    }

    function proposalEvidence(card, chain, view) {
      const node = el("details");
      node.dataset.evidenceKey = "proposal:" + known(chain.proposal_id);
      node.open = expandedEvidence.has(node.dataset.evidenceKey);
      const facts = el("dl");
      pair(facts, "Full source title", known(chain.title));
      pair(facts, "Target", known(chain.target) + " · " + known(chain.target_type));
      pair(facts, "Verdict / lane", view.verdict + " / " + view.lane);
      pair(facts, "Acceptance", view.acceptance + " · " + (view.acceptedAt || "date unknown"));
      pair(facts, "Enactment", view.enactment + " · " + (view.enactedAt || "date unknown"));
      pair(facts, "Verification", view.verification + " · " + (view.reportedAt || "date unknown"));
      if (view.completeEnactment) {
        pair(facts, "Reported commit", view.evidence.commit);
        pair(facts, "Reported paths", view.evidence.paths.join(" · "));
      }
      const raw = el("pre", JSON.stringify({lifecycle: chain.lifecycle, healing: chain.healing, rule_cited: chain.rule_cited}, null, 2), "raw-evidence");
      add(node, el("summary", "Full lifecycle evidence and source"), facts,
        el("h4", "Raw supplied lifecycle"), raw,
        el("p", "Source: memory/brain/proposals.jsonl · " + known(chain.proposal_id) + "; projected lifecycle, physical line cursor unavailable", "source-ref"));
      card.appendChild(node);
    }

    function options(id, values, label) {
      const select = get(id), chosen = select.value;
      clear(select); const all = el("option", label); all.value = ""; select.appendChild(all);
      Array.from(new Set(values.filter(value => typeof value === "string" && value))).sort().forEach(value => {
        const option = el("option", value); option.value = value; select.appendChild(option);
      });
      if (chosen && !values.includes(chosen)) { const option = el("option", chosen + " (absent from this response)"); option.value = chosen; select.appendChild(option); }
      select.value = chosen || "";
    }

    function render(state) {
      const hosts = ["activity-list", "actors-list", "usage-list", "skills-list", "lifecycle-overview", "proposals-list", "candidates-list", "blockers-list"];
      const d = state.data;
      const attention = d ? attentionItems(d) : null;
      const malformed = d ? [d.skills, d.agents, d.timeline, d.matrix.cells, d.loop.chains].reduce((n, values) => n + values.filter(value => !object(value)).length, attention.malformed) : 0;
      showSource(state, malformed, attention && attention.error);
      // Fresh response metadata alone must not replace controls being read.
      const key = JSON.stringify([d ? {...d, generated_at: null} : null,
        activePanel, Array.from(pages.entries()), get("activity-search").value, get("actor-filter").value, get("skill-filter").value]);
      if (key === lastRenderKey) return;
      lastRenderKey = key;
      hosts.forEach(id => {
        if (id === "lifecycle-overview" && !get(id)) return;
        get(id).querySelectorAll("details[data-evidence-key]").forEach(node => {
          if (node.open) expandedEvidence.add(node.dataset.evidenceKey);
          else expandedEvidence.delete(node.dataset.evidenceKey);
        });
        clear(get(id));
      });
      if (!d) {
        get("activity-range").textContent = "No recorded range available.";
        const recovery = /^https?:$/.test(runtime.location.protocol) ? "Refresh to try again" : "Open this page through the existing brain UI or restore a valid generated snapshot";
        const activeHosts = {activity: ["activity-list"], actors: ["actors-list", "usage-list"], skills: ["skills-list"], proposals: ["proposals-list"], candidates: ["candidates-list"], blockers: ["blockers-list"]};
        activeHosts[activePanel].forEach(id => empty(get(id), "Evidence unavailable. " + recovery + "; absence is not a successful outcome."));
        return;
      }
      showLifecycleOverview(d.loop.chains);
      const agents = new Map(d.agents.filter(object).map(agent => [agent.id, agent]));
      options("actor-filter", d.agents.filter(object).map(a => a.id).concat(d.timeline.filter(object).map(t => t.agent), d.matrix.cells.filter(object).map(c => c.agent)), "All recorded actors");
      options("skill-filter", d.skills.filter(object).map(skill => skill.name).concat(
        d.timeline.filter(object).map(row => row.skill), d.matrix.cells.filter(object).map(cell => cell.skill),
        d.loop.chains.filter(object).filter(chain => chain.target_type === "skill").map(chain => chain.target),
        attention.items.map(item => object(item.link) ? item.link.skill : null)), "All skills");
      const query = get("activity-search").value.trim().toLowerCase();
      const actor = get("actor-filter").value, selectedSkill = get("skill-filter").value;
      const matches = value => !query || text(value).toLowerCase().includes(query);
      const skillMatch = value => !selectedSkill || value === selectedSkill;
      const skills = d.skills.filter(object).filter(skill => skillMatch(skill.name) && matches([skill.name, skill.purpose, skill.pack]));
      const chains = d.loop.chains.filter(object).filter(chain => skillMatch(chain.target) && matches([chain.proposal_id, chain.title, chain.target, chain.final_verdict, chain.lane, rows(chain.lifecycle).filter(row => object(row)).map(row => row.actor)]));
      if (activePanel === "activity") {
        get("activity-range").textContent = "Supplied recorded range: " + (recordedTime(d.window.oldest_event) || "unknown") + " → " +
          (recordedTime(d.window.newest_event) || "unknown") + ". Recent supplied timestamps appear first; this bounded timeline is not a complete run ledger or current-session list.";
        const activity = d.timeline.filter(object).filter(row => (!actor || row.agent === actor) && skillMatch(row.skill) && matches([row.title, row.id, row.agent, row.skill, row.kind]))
          .sort((left, right) => (recordedTime(right.ts) || recordedTime(right.date) || "").localeCompare(recordedTime(left.ts) || recordedTime(left.date) || ""));
        if (!activity.length) empty(get("activity-list"), "No recorded activity matches these filters in the supplied timeline.");
        else {
          const host = get("activity-list");
          const body = table(host, ["Time", "Actor", "Task", "Outcome", "Evidence"], activity.length + " matching timeline rows · 12 per page");
          page(host, "activity", activity, visible => visible.forEach(row => {
            const actorRecord = agents.get(row.agent);
            const actorEvidence = actorRecord ? "registry: " + known(actorRecord.evidence) + "; event attribution provenance not supplied" : "not resolved in supplied actor registry";
            const evidence = el("td", undefined, "activity-evidence");
            const record = el("details"); record.dataset.evidenceKey = "activity:" + known(row.id); record.open = expandedEvidence.has(record.dataset.evidenceKey);
            add(record, el("summary", "Evidence & source"), el("p", "Actor: " + known(row.agent) + " · " + actorEvidence, "source-ref"),
              el("p", "Skill label: " + known(row.skill) + "; kind: " + known(row.kind) + "; record: " + known(row.id), "source-ref"),
              el("p", "summary.timeline — supplied row cursor unavailable", "source-ref"));
            evidence.appendChild(record);
            tr(body, [el("td", recordedTime(row.ts) || "Unknown / invalid recorded time", "compact-cell"), el("td", known(row.agent), "compact-cell"),
              el("td", known(row.title), "compact-cell"), el("td", known(row.verdict)), evidence]);
          }));
        }
      }
      if (activePanel === "actors") {
        const actorRows = d.agents.filter(object).filter(row => (!actor || row.id === actor) && matches(row.id));
        if (!actorRows.length) empty(get("actors-list"), "No matching actor records supplied.");
        else {
          const host = get("actors-list"); const body = table(host, ["Actor label", "Registry evidence", "Recorded observation span", "Reported actor metadata"], "Actor labels are unauthenticated; registry presence is not liveness");
          page(host, "actors", actorRows, visible => visible.forEach(row => {
            const referenceOnly = row.evidence === "inferred" && !row.first_seen && !row.last_seen && object(row.runs_by_day) && !Object.keys(row.runs_by_day).length;
            const crypto = row.cryptographically_authenticated === false ? "no (assertion only)" : row.cryptographically_authenticated === true ? "unsupported claim" : "unknown";
            tr(body, [known(row.id), known(row.evidence), referenceOnly ? "Reference only · no recorded run presence; observation time unavailable" :
              (recordedTime(row.first_seen) || "Unknown first observation") + " → " + (recordedTime(row.last_seen) || "Unknown last observation"),
            "source: " + known(row.actor_source) + " · type: " + known(row.actor_type) + " · reported authentication: " + known(row.authentication) + " · cryptographic authentication: " + crypto]);
          }));
          source(host, "summary.agents; registry evidence does not determine the provenance of each timeline event");
        }
        const cells = d.matrix.cells.filter(object).filter(cell => (!actor || cell.agent === actor) && skillMatch(cell.skill) && matches([cell.agent, cell.skill]));
        if (!cells.length) empty(get("usage-list"), "No matching attribution in the supplied matrix.");
        else {
          const host = get("usage-list"); const body = table(host, ["Actor / skill", "Explicit usage labels", "Inferred references", "Last attributed date", "Attribution methods"], "Attribution totals supplied by the projection");
          page(host, "usage", cells, visible => visible.forEach(cell => tr(body, [known(cell.agent) + " / " + known(cell.skill), count(cell.explicit), count(cell.inferred), recordedTime(cell.last) || "Unknown",
            object(cell.methods) ? Object.entries(cell.methods).map(([method, value]) => method + ": " + count(value)).join(" · ") : "Unknown"])));
          source(host, "summary.matrix.cells; historical references can predate the timeline range");
        }
      }
      if (activePanel === "skills") {
        if (!skills.length) empty(get("skills-list"), "No matching skills in the supplied projection.");
        else page(get("skills-list"), "skills", skills, visible => visible.forEach(skill => {
          const card = el("article", undefined, "card skill-card"), governance = object(skill.governance) ? skill.governance : {};
          const conformance = object(governance.conformance) ? governance.conformance : {}, usage = object(skill.usage) ? skill.usage : {};
          const allowed = skill.runtime_safe === true ? "Declared runtime-safe" : skill.runtime_safe === false ? "Dev-time only" : "Runtime designation unknown";
          const head = el("div", undefined, "skill-head");
          add(head, el("h3", known(skill.name)), el("span", "Layer " + known(skill.layer), "pill accent"));
          add(card, head, el("p", known(skill.purpose), "skill-purpose"));
          const compare = el("div", undefined, "skill-comparison");
          const allowedCell = el("div"); add(allowedCell, el("strong", "Allowed use"), el("span", allowed + " · " + known(skill.pack) + " pack"));
          const historyCell = el("div"); add(historyCell, el("strong", "Historical attribution"), el("span", "Explicit labels " + count(usage.explicit) + " · inferred references " + count(usage.inferred)));
          const confirmedCell = el("div"); add(confirmedCell, el("strong", "Confirmed / friction"), el("span", count(conformance.confirmed) + " / " + count(conformance.friction)));
          const gapCell = el("div"); add(gapCell, el("strong", "Gaps / divergence"), el("span", count(conformance.gap) + " / " + count(conformance.diverged)));
          add(compare, allowedCell, historyCell, confirmedCell, gapCell); card.appendChild(compare);
          if (object(governance.drift) && governance.drift.active) add(card, el("p", "Friction or gap remains: " + known(governance.drift.open_note), "next-action"));
          if (governance.firewall_violation) add(card, el("p", "Reported boundary violation: owner review required.", "pill bad"));
          const record = el("details");
          record.dataset.evidenceKey = "skill:" + known(skill.name);
          record.open = expandedEvidence.has(record.dataset.evidenceKey);
          add(record, el("summary", "Inspect skill evidence"),
            el("p", "Recorded conformance: " + known(conformance.status) + ". Historical attribution does not grant runtime use or prove a successful outcome.", "source-note"),
            el("pre", JSON.stringify({governance, usage}, null, 2), "raw-evidence"));
          source(record, "summary.skills; .agents/skills/" + known(skill.name) + "/SKILL.md; memory/feedback.jsonl (row cursor unavailable)");
          card.appendChild(record); get("skills-list").appendChild(card);
        }));
      }
      if (activePanel === "proposals") {
        if (!chains.length) empty(get("proposals-list"), "No matching proposals in the supplied projection.");
        else page(get("proposals-list"), "proposals", chains, visible => {
          const host = get("proposals-list");
          const addGroup = (label, values, className) => {
            if (!values.length) return;
            const group = el("section", undefined, "proposal-group " + className);
            group.setAttribute("aria-label", label);
            group.appendChild(el("h3", label, "proposal-group-title"));
            values.forEach(chain => {
              const view = lifecycle(chain), card = el("article", undefined, "card proposal-card");
              add(card, el("h3", known(chain.proposal_id) + " · " + compactTitle(chain.title)),
                el("p", known(chain.target) + " · Current stage · " + view.stage, "stage-line"));
              if (view.contradiction) add(card, el("p", "Contradictory supplied lifecycle evidence", "pill bad"));
              const track = el("div", undefined, "lifecycle-track");
              [["Acceptance", view.acceptance], ["Enactment", view.enactment], ["Verification", view.verification]].forEach(([label, value]) => {
                const step = el("div", undefined, "lifecycle-step"); add(step, el("b", label), el("span", value)); track.appendChild(step);
              });
              add(card, track, el("p", "Required next evidence · " + view.next, "next-action"));
              const link = inspectLink(chain.proposal_id); if (link) card.appendChild(link);
              proposalEvidence(card, chain, view); group.appendChild(card);
            });
            host.appendChild(group);
          };
          // A closed decision is not a completed repair. This view has no
          // independent outcome verifier, so reported passes still need inspection.
          const history = chain => !lifecycle(chain).contradiction &&
            (chain.lane === "rejected" || ["rejected", "auto-reject"].includes(chain.final_verdict));
          addGroup("Lifecycle evidence to inspect", visible.filter(chain => !history(chain)), "proposal-current");
          addGroup("Recorded rejection history", visible.filter(history), "proposal-history");
        });
      }
      if (activePanel === "candidates") {
        const candidates = chains.filter(chain => chain.target_type === "skill" && ["draft", "open", "human-review"].includes(chain.lane));
        const gaps = skills.filter(skill => object(skill.governance) && object(skill.governance.conformance) && Number(skill.governance.conformance.gap) > 0);
        const candidateRows = candidates.map(chain => ({type: "proposal", value: chain})).concat(gaps.map(skill => ({type: "gap", value: skill})));
        if (!candidateRows.length) empty(get("candidates-list"), "No matching skill candidates or recorded gaps supplied. This does not establish that the backlog is complete.");
        else page(get("candidates-list"), "candidates", candidateRows, visible => visible.forEach(item => {
          const card = el("article", undefined, "card");
          if (item.type === "proposal") {
            const chain = item.value, view = lifecycle(chain); card.className += " candidate-card";
            const stage = view.contradiction ? "Contradiction needs reconciliation" : chain.lane === "draft" ? "Draft held" : "Awaiting governed Review";
            const next = view.contradiction ? "Reconcile source records." : chain.lane === "draft" ? "Graduation record required (graduation closed)." : "Inspect supporting evidence before a decision.";
            add(card, el("h3", known(chain.proposal_id) + " · " + compactTitle(chain.title)),
              el("p", known(chain.target) + " · " + stage, "stage-line"));
            if (view.contradiction) add(card, el("p", "Contradictory supplied lifecycle evidence", "pill bad"));
            add(card, el("p", chain.lane === "draft" && !view.contradiction ? "Next: graduation closed" : "Next: " + next, "next-action"));
            const link = inspectLink(chain.proposal_id); if (link) card.appendChild(link);
            details(card, "Full source", known(chain.title) + "\nTarget: " + known(chain.target) + " · Stage: " + stage + "\nNext evidence · " + next + "\nmemory/brain/proposals.jsonl · " + known(chain.proposal_id), "candidate:" + known(chain.proposal_id));
          }
          else { const skill = item.value; add(card, el("h3", "Feedback gaps: " + known(skill.name)), el("p", count(skill.governance.conformance.gap) + " recorded gaps. Owner: inspect the feedback before proposing a skill or section change.")); source(card, "memory/feedback.jsonl; exact feedback rows not supplied"); }
          get("candidates-list").appendChild(card);
        }));
      }
      if (activePanel === "blockers") {
        const host = get("blockers-list"); add(host, el("p", attention.note, "source-note"));
        const inbox = attention.items.filter(item => skillMatch(object(item.link) ? item.link.skill : null) && matches([item.id, item.title, item.detail, item.kind]));
        if (!inbox.length) empty(host, "No matching attention items supplied. Missing evidence and unreported failures may remain.");
        else page(host, "blockers", inbox, visible => visible.forEach(item => {
          const card = el("article", undefined, "card"); add(card, el("h3", known(item.title)), el("span", known(item.severity) + " · " + known(item.kind), "pill warn"), el("p", known(item.detail)));
          add(card, el("p", item.attentionGroup + (item.actionable === false ? " · view-only" : " · source review"), "source-note"), el("p", item.actionable === false ? "Owner: inspect the source; this projection supplies no actionable resolution." : "Owner: review the source and follow the existing governed workflow.", "next-action"));
          if (item.action_cmd) details(card, "Reported next action (text only; not executed)", text(item.action_cmd), "attention:" + known(item.id)); source(card, known(item.source) + " · " + known(item.id)); host.appendChild(card);
        }));
      }
      lastRenderKey = JSON.stringify([d ? {...d, generated_at: null} : null,
        activePanel, Array.from(pages.entries()), get("activity-search").value, get("actor-filter").value, get("skill-filter").value]);
    }

    store = createStore(runtime, runtime.BRAIN_SUMMARY, render);
    const panels = {activity: "activity-section", actors: "actors-section", skills: "skills-section", proposals: "proposals-section", candidates: "candidates-section", blockers: "blockers-section"};
    const tabNames = Object.keys(panels);
    const activatePanel = (name, moveFocus) => {
      activePanel = name;
      Object.entries(panels).forEach(([candidate, section]) => {
        const selected = candidate === activePanel;
        get(candidate + "-tab").setAttribute("aria-selected", String(selected));
        get(candidate + "-tab").setAttribute("tabindex", selected ? "0" : "-1");
        get(section).hidden = !selected;
      });
      if (moveFocus) get(name + "-tab").focus();
      render(store);
    };
    tabNames.forEach((name, index) => {
      const tab = get(name + "-tab");
      tab.addEventListener("click", () => activatePanel(name, false));
      tab.addEventListener("keydown", event => {
        let next;
        if (event.key === "ArrowLeft") next = (index - 1 + tabNames.length) % tabNames.length;
        else if (event.key === "ArrowRight") next = (index + 1) % tabNames.length;
        else if (event.key === "Home") next = 0;
        else if (event.key === "End") next = tabNames.length - 1;
        else return;
        event.preventDefault();
        activatePanel(tabNames[next], true);
      });
    });
    get("activity-filters").addEventListener("submit", event => event.preventDefault());
    ["activity-search", "actor-filter", "skill-filter"].forEach(id => get(id).addEventListener(id === "activity-search" ? "input" : "change", () => { resetPages(); render(store); }));
    get("clear-filters").addEventListener("click", () => { ["activity-search", "actor-filter", "skill-filter"].forEach(id => { get(id).value = ""; }); resetPages(); render(store); get("activity-search").focus(); });
    get("refresh-data").addEventListener("click", () => store.refresh());
    render(store);
    if (/^https?:$/.test(runtime.location.protocol)) store.refresh();
    const networkPage = /^https?:$/.test(runtime.location.protocol);
    get("auto-refresh").disabled = !networkPage;
    if (!networkPage) get("auto-refresh").checked = false;
    const timer = networkPage ? runtime.setInterval(() => { if (!document.hidden && get("auto-refresh").checked && !store.loading) store.refresh(); }, 30000) : null;
    runtime.addEventListener("pagehide", event => {
      if (event && event.persisted) return; // BFCache retains this page and its controls.
      if (timer !== null) runtime.clearInterval(timer); store.dispose();
    });
    runtime.addEventListener("pageshow", event => {
      if (event && event.persisted && networkPage && get("auto-refresh").checked) return store.refresh();
    });
    return store;
  }
  root.Activity = {validSummary, recordedTime, createStore, lifecycle, lifecycleCounts, proposalHref, mount};
  if (root.document && root.document.getElementById("activity-root")) root.activityStore = mount(root, root.document);
})(window);
