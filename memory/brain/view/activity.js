// Read-only view of one supplied summary. No actor authentication or ledger writes.
(function (root) {
  "use strict";
  const object = value => value && typeof value === "object" && !Array.isArray(value);
  const text = value => typeof value === "string" ? value : value == null ? "Unknown" : JSON.stringify(value);
  const rows = value => Array.isArray(value) ? value : [];
  const count = value => Number.isInteger(value) && value >= 0 ? String(value) : "Unknown";
  const known = value => typeof value === "string" && value.trim() ? value : "Unknown";

  function validSummary(data) {
    return !!(object(data) && data.schema_version === 2 && object(data.window) &&
      Array.isArray(data.agents) && Array.isArray(data.skills) && Array.isArray(data.timeline) &&
      Array.isArray(data.inbox) && object(data.matrix) && Array.isArray(data.matrix.cells) &&
      object(data.loop) && Array.isArray(data.loop.chains));
  }

  function attentionItems(data) {
    const keys = ["framework_actions", "external_acknowledgements", "backlog_history"];
    const canonical = object(data.attention) && keys.every(key => Array.isArray(data.attention[key]));
    if (!canonical) return {note: "Legacy inbox projection · view-only; governed attention partitions unavailable", items:
      data.inbox.filter(object).map(item => ({...item, actionable: false, action_cmd: null, attentionGroup: "legacy inbox"}))};
    return {note: "Supplied attention partitions; external acknowledgements are view-only", items: keys.flatMap(key =>
      data.attention[key].filter(object).map(item => {
        const external = key === "external_acknowledgements" || item.surface !== "framework";
        return {...item, attentionGroup: key.replaceAll("_", " "),
          ...(external ? {actionable: false, action_cmd: null} : {})};
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
      if (revision === 0 && !disposed) { state.hash = hash; changed(state); }
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
    if (rejected) next = "Owner: retain the rejection and its reason; any new proposal needs a separate review.";
    else if (enacted.state === "enacted" && !completeEnactment) next = "Owner: provide the implementation commit and paths in the canonical enactment evidence before assessing verification.";
    else if (accepted.state === "accepted" && enacted.state !== "enacted") next = "Owner: provide a reviewed implementation commit and matching changed paths.";
    else if (completeEnactment) next = "Owner: independently verify execution and results against this implementation; a reported pass is insufficient.";
    if (contradiction) next = "Owner: reconcile the contradictory verdict and lifecycle projection against the original records.";
    return {
      verdict: known(chain.final_verdict), lane: known(chain.lane),
      acceptance: rejected ? "Rejected verdict" : accepted.state === "accepted" ? "Recorded acceptance" : "Acceptance unknown / pending",
      enactment: completeEnactment ? "Projector-reported Git/path evidence" : enacted.state === "enacted" ? "Incomplete enactment claim; evidence unavailable" : "Enactment " + known(enacted.state).toLowerCase(),
      // This page has no independent execution verifier, even for a supplied label.
      verification: object(verified.reported) ? "Reported verification · pending" : "Independent verification not established",
      acceptedAt: recordedTime(accepted.at), enactedAt: recordedTime(enacted.at),
      reportedAt: object(verified.reported) ? recordedTime(verified.reported.at) : null,
      contradiction, next, healing, completeEnactment, evidence
    };
  }

  function mount(runtime, document) {
    const expandedEvidence = new Set();
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
    const table = (host, headings, caption) => {
      const wrap = el("div", undefined, "table-scroll"), grid = el("table"), head = el("thead"), tr = el("tr"), body = el("tbody");
      headings.forEach(label => { const th = el("th", label); th.setAttribute("scope", "col"); tr.appendChild(th); });
      add(head, tr); add(grid, el("caption", caption), head, body); add(wrap, grid); host.appendChild(wrap); return body;
    };
    const tr = (host, values) => { const row = el("tr"); values.forEach(value => row.appendChild(el("td", value))); host.appendChild(row); };
    let store;
    const stateLabel = state => !state.data ? "Data unavailable" : state.source === "snapshot" ? "Snapshot data" : state.error ? "Cached response · refresh failed" : "Live response received";
    function showSource(state, malformed) {
      const label = stateLabel(state);
      get("data-state").textContent = label + (state.loading ? " · checking for an update…" : "");
      const warning = (state.error || "") + (malformed ? " " + malformed + " malformed rows could not be displayed; this view is incomplete." : "");
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
      pair(host, "Trust", "A fresh response does not prove fresh underlying events, authenticated actors or verified execution.");
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
      const hosts = ["activity-list", "actors-list", "usage-list", "skills-list", "proposals-list", "candidates-list", "blockers-list"];
      const d = state.data;
      const malformed = d ? [d.skills, d.agents, d.timeline, d.matrix.cells, d.loop.chains, d.inbox].reduce((n, values) => n + values.filter(value => !object(value)).length, 0) : 0;
      showSource(state, malformed);
      // Fresh response metadata alone must not replace controls being read.
      const key = JSON.stringify([d ? {...d, generated_at: null} : null,
        get("activity-search").value, get("actor-filter").value, get("skill-filter").value]);
      if (key === lastRenderKey) return;
      lastRenderKey = key;
      hosts.forEach(id => {
        get(id).querySelectorAll("details[data-evidence-key]").forEach(node => {
          if (node.open) expandedEvidence.add(node.dataset.evidenceKey);
          else expandedEvidence.delete(node.dataset.evidenceKey);
        });
        clear(get(id));
      });
      if (!d) {
        get("activity-range").textContent = "No recorded range available.";
        const recovery = /^https?:$/.test(runtime.location.protocol) ? "Refresh to try again" : "Open this page through the existing brain UI or restore a valid generated snapshot";
        hosts.forEach(id => empty(get(id), "Evidence unavailable. " + recovery + "; absence is not a successful outcome."));
        return;
      }
      const attention = attentionItems(d);
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
      get("activity-range").textContent = "Supplied recorded range: " + (recordedTime(d.window.oldest_event) || "unknown") + " → " +
        (recordedTime(d.window.newest_event) || "unknown") + ". Timeline is a bounded projection; it is not a complete run ledger or a current-session list.";
      const activity = d.timeline.filter(object).filter(row => (!actor || row.agent === actor) && skillMatch(row.skill) && matches([row.title, row.id, row.agent, row.skill, row.kind]));
      if (!activity.length) empty(get("activity-list"), "No recorded activity matches these filters in the supplied timeline.");
      else {
        const body = table(get("activity-list"), ["Recorded time", "Actor label", "Activity", "Recorded outcome", "Skill / evidence"], activity.length + " supplied timeline rows match");
        activity.forEach(row => {
          const actorRecord = agents.get(row.agent);
          const actorEvidence = actorRecord ? "registry: " + known(actorRecord.evidence) + "; event attribution provenance not supplied" : "not resolved in supplied actor registry";
          tr(body, [recordedTime(row.ts) || "Unknown / invalid recorded time", known(row.agent) + " · " + actorEvidence,
            known(row.title) + " [" + known(row.kind) + "] · " + known(row.id), known(row.verdict), known(row.skill) + " · timeline label; usage attribution is below"]);
        });
        source(get("activity-list"), "summary.timeline — supplied order retained; underlying row cursor not provided");
      }
      const actorRows = d.agents.filter(object).filter(row => (!actor || row.id === actor) && matches(row.id));
      if (!actorRows.length) empty(get("actors-list"), "No matching actor records supplied.");
      else {
        const body = table(get("actors-list"), ["Actor label", "Registry evidence", "Recorded observation span"], "Actor labels are unauthenticated; registry presence is not liveness");
        actorRows.forEach(row => {
          const referenceOnly = row.evidence === "inferred" && !row.first_seen && !row.last_seen && object(row.runs_by_day) && !Object.keys(row.runs_by_day).length;
          tr(body, [known(row.id), known(row.evidence), referenceOnly ? "Reference only · no recorded run presence; observation time unavailable" :
            (recordedTime(row.first_seen) || "Unknown first observation") + " → " + (recordedTime(row.last_seen) || "Unknown last observation")]);
        });
        source(get("actors-list"), "summary.agents; registry evidence does not determine the provenance of each timeline event");
      }
      const cells = d.matrix.cells.filter(object).filter(cell => (!actor || cell.agent === actor) && skillMatch(cell.skill) && matches([cell.agent, cell.skill]));
      if (!cells.length) empty(get("usage-list"), "No matching attribution in the supplied matrix.");
      else {
        const body = table(get("usage-list"), ["Actor / skill", "Explicit usage labels", "Inferred references", "Last attributed date", "Attribution methods"], "Attribution totals supplied by the projection");
        cells.forEach(cell => tr(body, [known(cell.agent) + " / " + known(cell.skill), count(cell.explicit), count(cell.inferred), recordedTime(cell.last) || "Unknown",
          object(cell.methods) ? Object.entries(cell.methods).map(([method, value]) => method + ": " + count(value)).join(" · ") : "Unknown"]));
        source(get("usage-list"), "summary.matrix.cells; historical references can predate the timeline range");
      }

      const skills = d.skills.filter(object).filter(skill => skillMatch(skill.name) && matches([skill.name, skill.purpose, skill.pack]));
      skills.forEach(skill => {
        const card = el("article", undefined, "card skill-card"), governance = object(skill.governance) ? skill.governance : {};
        const conformance = object(governance.conformance) ? governance.conformance : {}, usage = object(skill.usage) ? skill.usage : {};
        add(card, el("h3", known(skill.name)), el("p", known(skill.purpose)));
        add(card, el("span", "Layer " + known(skill.layer), "pill"), el("span", known(skill.pack), "pill"),
          el("span", skill.runtime_safe === true ? "Declared runtime-safe" : skill.runtime_safe === false ? "Dev-time only" : "Runtime designation unknown", "pill"));
        const dl = el("dl"); pair(dl, "Explicit / inferred usage", count(usage.explicit) + " / " + count(usage.inferred));
        pair(dl, "Confirmed / friction", count(conformance.confirmed) + " / " + count(conformance.friction));
        pair(dl, "Gaps / divergence", count(conformance.gap) + " / " + count(conformance.diverged));
        pair(dl, "Recorded conformance", known(conformance.status)); add(card, dl);
        if (object(governance.drift) && governance.drift.active) add(card, el("p", "Friction or gap remains: " + known(governance.drift.open_note), "next-action"));
        if (governance.firewall_violation) add(card, el("p", "Reported boundary violation: owner review required.", "pill bad"));
        source(card, "summary.skills; .agents/skills/" + known(skill.name) + "/SKILL.md; memory/feedback.jsonl (row cursor unavailable)");
        get("skills-list").appendChild(card);
      });
      if (!skills.length) empty(get("skills-list"), "No matching skills in the supplied projection.");

      const chains = d.loop.chains.filter(object).filter(chain => skillMatch(chain.target) && matches([chain.proposal_id, chain.title, chain.target, chain.final_verdict, chain.lane, rows(chain.lifecycle).filter(object).map(row => row.actor)]));
      chains.forEach(chain => {
        const view = lifecycle(chain), card = el("article", undefined, "card proposal-card");
        add(card, el("h3", known(chain.proposal_id) + " · " + known(chain.title)), el("p", "Target: " + known(chain.target) + " · " + known(chain.target_type)),
          el("span", "Verdict: " + view.verdict, "pill"), el("span", "Lane: " + view.lane, "pill"));
        const dl = el("dl"); pair(dl, "Acceptance", view.acceptance + " · " + (view.acceptedAt || "date unknown"));
        pair(dl, "Enactment", view.enactment + " · " + (view.enactedAt || "date unknown"));
        pair(dl, "Verification", view.verification + " · " + (view.reportedAt || "date unknown")); add(card, dl);
        if (view.completeEnactment) { pair(dl, "Reported commit", view.evidence.commit); pair(dl, "Reported paths", view.evidence.paths.join(" · ")); }
        if (view.contradiction) add(card, el("p", "Contradictory supplied lifecycle evidence", "pill bad"));
        add(card, el("p", view.next, "next-action"));
        details(card, "Recorded lifecycle and evidence", JSON.stringify({lifecycle: chain.lifecycle, healing: chain.healing, rule_cited: chain.rule_cited}, null, 2), "proposal:" + known(chain.proposal_id));
        source(card, "memory/brain/proposals.jsonl · " + known(chain.proposal_id) + "; projected lifecycle, physical line cursor unavailable");
        get("proposals-list").appendChild(card);
      });
      if (!chains.length) empty(get("proposals-list"), "No matching proposals in the supplied projection.");

      const candidates = chains.filter(chain => chain.target_type === "skill" && ["draft", "open", "human-review"].includes(chain.lane));
      const gaps = skills.filter(skill => object(skill.governance) && object(skill.governance.conformance) && Number(skill.governance.conformance.gap) > 0);
      candidates.forEach(chain => {
        const card = el("article", undefined, "card"); add(card, el("h3", known(chain.proposal_id) + " · " + known(chain.title)), el("p", "Recorded skill proposal · " + known(chain.lane) + ". Consider through the existing owner review workflow."));
        source(card, "memory/brain/proposals.jsonl · " + known(chain.proposal_id)); get("candidates-list").appendChild(card);
      });
      gaps.forEach(skill => { const card = el("article", undefined, "card"); add(card, el("h3", "Feedback gaps: " + known(skill.name)), el("p", count(skill.governance.conformance.gap) + " recorded gaps. Owner: inspect the feedback before proposing a skill or section change.")); source(card, "memory/feedback.jsonl; exact feedback rows not supplied"); get("candidates-list").appendChild(card); });
      if (!candidates.length && !gaps.length) empty(get("candidates-list"), "No matching skill candidates or recorded gaps supplied. This does not establish that the backlog is complete.");

      add(get("blockers-list"), el("p", attention.note, "source-note"));
      const inbox = attention.items.filter(item => skillMatch(object(item.link) ? item.link.skill : null) && matches([item.id, item.title, item.detail, item.kind]));
      inbox.forEach(item => {
        const card = el("article", undefined, "card"); add(card, el("h3", known(item.title)), el("span", known(item.severity) + " · " + known(item.kind), "pill warn"), el("p", known(item.detail)));
        add(card, el("p", item.attentionGroup + (item.actionable === false ? " · view-only" : " · source review"), "source-note"));
        add(card, el("p", item.actionable === false ? "Owner: inspect the source; this projection supplies no actionable resolution." : "Owner: review the source and follow the existing governed workflow.", "next-action"));
        if (item.action_cmd) details(card, "Reported next action (text only; not executed)", text(item.action_cmd), "attention:" + known(item.id));
        source(card, known(item.source) + " · " + known(item.id)); get("blockers-list").appendChild(card);
      });
      if (!inbox.length) empty(get("blockers-list"), "No matching attention items supplied. Missing evidence and unreported failures may remain.");
    }

    store = createStore(runtime, runtime.BRAIN_SUMMARY, render);
    get("activity-filters").addEventListener("submit", event => event.preventDefault());
    ["activity-search", "actor-filter", "skill-filter"].forEach(id => get(id).addEventListener(id === "activity-search" ? "input" : "change", () => render(store)));
    get("clear-filters").addEventListener("click", () => { ["activity-search", "actor-filter", "skill-filter"].forEach(id => { get(id).value = ""; }); render(store); get("activity-search").focus(); });
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
  root.Activity = {validSummary, recordedTime, createStore, lifecycle, mount};
  if (root.document && root.document.getElementById("activity-root")) root.activityStore = mount(root, root.document);
})(window);
