#!/usr/bin/env python3
"""project_map.py — project the GOVERNANCE graph into map_data.js.

Emits `memory/brain/view/map_data.js` — `window.BRAIN_MAP = {generated_at,
nodes, edges, cards}` — for the agent↔skill cluster map (map.js / BrainMap).
Replaces the retired whole-brain graph_data.js: governance entities ONLY
(skills, agents, proposals, rules, harvest findings, recent spawns,
corrections, anomalies, linked decisions). No stage / llm_call /
apparatus_event / orchestrator_event nodes — that plumbing lives in the
apparatus dashboard, not the brain map.

Edges = the governance chain (about/targets/becomes/produces/enacts/extends/
references/uses/authored/filed/launched + whatever typed edges.jsonl rows
connect two governance entities) PLUS one `used` edge per (agent, skill) cell
of the attribution ladder (parity with scripts/project_summary.py):

  rung 1  explicit run-log `skill_used`                       → explicit (e)
  rung 2  status semantics (failed/escalated/gate_armed/…)    → inferred (i)
  rung 3  task_id patterns (gate./harvest/validate/sp_/…)     → inferred (i)
  rung 4  feedback.jsonl findings → (nara, finding.skill)     → inferred (i)
  rung 5  spawn-contract skill_subset → (spawn agent, skill)  → inferred (i)

Per-file run-log agent defaults (FR-003 read-time canonicalization):
week1.run.jsonl → nara, framework.run.jsonl → claude-code-main. Raw agent
labels canonicalize via project_pages.canonicalize_agent; workflow:<role>
collapses to the single map actor `workflow` (one node, m1 layout slot).

cards = one-line summaries (≤220 chars) + page path — NO markdown bodies.
Budget: ≤400 nodes, <300 KB. Deterministic; compare-before-write excludes
generated_at so an unchanged rerun touches nothing. Read-only on the consumer
(brain firewall). Consumer resolution: $BRAIN_CONSUMER_ROOT if set, else a
walk-up from this script's location for a sibling a_bgt_rsi containing
memory/loop_memory.jsonl — never REPO.parent (worktrees resolve to a void).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from project_pages import (  # noqa: E402
    REPO,
    EDGES,
    NARRATIVES,
    PROPOSALS,
    FEEDBACK,
    SPAWN_LEDGER,
    FW_DECISIONS,
    canonicalize_agent,
    load_decisions,
    load_jsonl,
    load_rules,
    load_skills,
    narrative_slug,
    slugify,
)

OUT_JS = REPO / "memory" / "brain" / "view" / "map_data.js"
PAGES_DIR = REPO / "memory" / "brain" / "pages"
FW_RUN = REPO / "run_state" / "framework.run.jsonl"
CONFORMANCE = REPO / "memory" / "conformance.md"

MAX_NODES = 400
MAX_BYTES = 300_000
RECENT_SPAWN_DAYS = 45
ONE_LINE_CAP = 220

EXCLUDED_TYPES = {"stage", "llm_call", "apparatus_event", "orchestrator_event",
                  "iteration", "run_log_entry"}

# Attribution ladder rung 2 — status semantics (parity with project_summary).
STATUS_TO_SKILL = {
    "failed": "validate",
    "partial_pass": "validate",
    "aborted": "validate",
    "recovered": "validate",
    "escalated": "fallback",
    "human_gate_blocked": "gate-check",
    "gate_armed": "gate-check",
    "declared": "slip-ladder",
}

EXTENDS_RE = re.compile(r"extends\s+(?:the\s+)?\[\[([a-z0-9-]+)\]\]")
DECISION_HEAD_RE = re.compile(r"^(D-\d+|\d{4}-\d{2}-\d{2})$")


def resolve_consumer() -> Path | None:
    """$BRAIN_CONSUMER_ROOT, else walk up from the script location for a
    sibling a_bgt_rsi that contains memory/loop_memory.jsonl."""
    env = os.environ.get("BRAIN_CONSUMER_ROOT")
    if env:
        p = Path(env).expanduser()
        return p.resolve() if p.exists() else None
    cur = _SCRIPTS
    for _ in range(8):
        cand = cur / "a_bgt_rsi"
        if (cand / "memory" / "loop_memory.jsonl").exists():
            return cand.resolve()
        if cur.parent == cur:
            break
        cur = cur.parent
    return None


def one_line(s: str | None, cap: int = ONE_LINE_CAP) -> str:
    s = " ".join((s or "").split())
    return s if len(s) <= cap else s[: cap - 1] + "…"


def date_of(iso: str | None) -> str:
    return (iso or "")[:10]


def map_agent(raw: str | None, default: str) -> str:
    """Canonical map actor for a run-log/ledger row. workflow:<role> ids
    collapse to the single `workflow` actor (one node on the map)."""
    c = canonicalize_agent(raw)
    if not c:
        return default
    if c == "workflow" or c.startswith("workflow:"):
        return "workflow"
    return c


def ladder_attribution(row: dict) -> tuple[str | None, bool]:
    """(skill, explicit?) for one run-log row — rungs 1-3. None = no rung."""
    sk = (row.get("skill_used") or "").strip()
    if sk:
        return sk, True
    st = (row.get("status") or "").strip()
    if st in STATUS_TO_SKILL:
        return STATUS_TO_SKILL[st], False
    task = (row.get("task_id") or "").strip()
    if task:
        if task.startswith("gate."):
            return "gate-check", False
        if "harvest" in task:
            return "harvest", False
        if "validate" in task:
            return "validate", False
        if task.startswith("sp_") or "spawn" in task:
            return "spawn-contract", False
        if "proposal" in task:
            return ("review-proposal" if "review" in task else "propose"), False
    return None, False


def conformance_status() -> dict[str, str]:
    """skill → status text from the per-skill conformance table (tolerant)."""
    out: dict[str, str] = {}
    try:
        text = CONFORMANCE.read_text()
    except OSError:
        return out
    row_re = re.compile(r"^\|\s*([a-z][a-z0-9-]*)\s*\|(?:[^|]*\|){5}\s*([^|]+)\|?\s*$",
                        re.MULTILINE)
    for m in row_re.finditer(text):
        out[m.group(1)] = " ".join(m.group(2).split())
    return out


def collapse_by_id(rows: list[dict], key: str) -> dict[str, list[dict]]:
    by_id: dict[str, list[dict]] = {}
    for r in sorted(rows, key=lambda x: x.get("timestamp", "")):
        rid = r.get(key)
        if rid:
            by_id.setdefault(rid, []).append(r)
    return by_id


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def build_map() -> dict:
    consumer = resolve_consumer()
    if consumer is None:
        print("warn: consumer not resolved — framework-side sources only",
              file=sys.stderr)

    nodes: dict[str, dict] = {}     # id -> {id,type,label,pack?,date?}
    cards: dict[str, dict] = {}     # id -> {title,date,one_line,source,page}
    edges: list[dict] = []

    def add_node(nid: str, ntype: str, label: str, *, pack: str | None = None,
                 date: str | None = None) -> None:
        n: dict = {"id": nid, "type": ntype, "label": label}
        if pack:
            n["pack"] = pack
        if date:
            n["date"] = date
        nodes.setdefault(nid, n)

    def add_card(nid: str, title: str, date: str, line: str, source: str) -> None:
        page = f"../pages/{nid}.md" if (PAGES_DIR / f"{nid}.md").is_file() else ""
        cards[nid] = {"title": one_line(title, 120), "date": date,
                      "one_line": one_line(line), "source": source, "page": page}

    def add_edge(src: str, dst: str, etype: str, *, e: int = 0, i: int = 0,
                 agent: str | None = None) -> None:
        edge: dict = {"src": src, "dst": dst, "type": etype}
        if e:
            edge["weight_e"] = e
        if i:
            edge["weight_i"] = i
        if agent:
            edge["agent"] = agent
        edges.append(edge)

    # ---- skills (all 24, the map's fixed cluster anatomy) -----------------
    skills_meta = load_skills()
    skill_names = {s["name"] for s in skills_meta}
    for s in skills_meta:
        nid = slugify(f"skill-{s['name']}")
        add_node(nid, "skill", s["name"], pack=s.get("pack") or "?")
        rt = "runtime-safe" if str(s["runtime_safe"]).lower() == "true" else "dev-time"
        add_card(nid, s["name"], "",
                 f"Layer {s['layer']} · {s.get('pack', '?')} · {rt} — {s['description']}",
                 f".agents/skills/{s['name']}/SKILL.md")
    skill_id = {name: slugify(f"skill-{name}") for name in skill_names}

    # ---- run-log attribution (rungs 1-3) ----------------------------------
    runlogs: list[tuple[str, Path]] = [("claude-code-main", FW_RUN)]
    if consumer is not None:
        runlogs.insert(0, ("nara", consumer / "run_state" / "week1.run.jsonl"))

    cells: dict[tuple[str, str], dict] = {}   # (agent, skill) -> {e,i,last}
    agent_seen: dict[str, dict] = {}          # agent -> {first,last,rows}

    def touch_agent(agent: str, ts: str) -> None:
        rec = agent_seen.setdefault(agent, {"first": "9999", "last": "", "rows": 0})
        rec["rows"] += 1
        if ts:
            rec["first"] = min(rec["first"], ts)
            rec["last"] = max(rec["last"], ts)

    def attribute(agent: str, skill: str, ts: str, explicit: bool) -> None:
        if skill not in skill_names:
            return
        c = cells.setdefault((agent, skill), {"e": 0, "i": 0, "last": ""})
        c["e" if explicit else "i"] += 1
        c["last"] = max(c["last"], date_of(ts))

    for default, path in runlogs:
        for row in load_jsonl(path):
            agent = map_agent(row.get("agent"), default)
            ts = row.get("timestamp") or ""
            touch_agent(agent, ts)
            skill, explicit = ladder_attribution(row)
            if skill:
                attribute(agent, skill, ts, explicit)

    # rung 4 — every harvest finding evidences nara exercising that skill
    feedback_rows = [f for f in load_jsonl(FEEDBACK) if f.get("harvest_id")]
    for f in feedback_rows:
        attribute("nara", (f.get("skill") or "").strip(),
                  (f.get("date") or "") + "T00:00:00Z", False)

    # ---- spawns (both ledgers, recent window) ------------------------------
    spawn_rows: list[tuple[str, dict]] = [("framework", r) for r in load_jsonl(SPAWN_LEDGER)]
    if consumer is not None:
        spawn_rows += [("apparatus", r)
                       for r in load_jsonl(consumer / "run_state" / "spawn.jsonl")]
    by_sid: dict[str, list[tuple[str, dict]]] = {}
    for surface, r in sorted(spawn_rows, key=lambda x: x[1].get("timestamp", "")):
        sid = r.get("spawn_id")
        if sid:
            by_sid.setdefault(sid, []).append((surface, r))

    all_dates: list[str] = [c["last"] for c in cells.values()]
    all_dates += [date_of(rows[0][1].get("timestamp")) for rows in by_sid.values()]
    all_dates += [f.get("date") or "" for f in feedback_rows]
    newest = max((d for d in all_dates if d), default=date_of(
        datetime.now(timezone.utc).isoformat()))

    def spawn_agent(sid: str, surface: str) -> str:
        if sid.startswith("SP-wf"):
            return "workflow"
        return "claude-code-main" if surface == "framework" else "nara"

    spawn_cut = None
    try:
        from datetime import date as _date, timedelta as _td
        spawn_cut = (_date.fromisoformat(newest) - _td(days=RECENT_SPAWN_DAYS)).isoformat()
    except ValueError:
        pass

    spawn_entries: list[tuple[str, str, dict, dict]] = []  # (sid,surface,first,latest)
    for sid, rows in by_sid.items():
        surface, first = rows[0]
        latest = rows[-1][1]
        d = date_of(first.get("timestamp"))
        if spawn_cut and d and d < spawn_cut:
            continue
        spawn_entries.append((sid, surface, first, latest))
    spawn_entries.sort(key=lambda t: (date_of(t[2].get("timestamp")), t[0]), reverse=True)
    spawn_entries = spawn_entries[:60]

    for sid, surface, first, latest in spawn_entries:
        nid = slugify(f"spawn-{sid}")
        contract = first.get("contract") or {}
        d = date_of(first.get("timestamp"))
        agent = spawn_agent(sid, surface)
        check = ((latest.get("result") or {}).get("done_condition_check")) or "—"
        add_node(nid, "spawn", sid, date=d)
        add_card(nid, f"{sid} — {first.get('child_task_id', 'spawn')}", d,
                 f"status {latest.get('status', '?')} · check {check} · "
                 f"{contract.get('task_statement', '')}",
                 ("run_state/spawn.jsonl" if surface == "framework"
                  else "a_bgt_rsi/run_state/spawn.jsonl"))
        for sk in contract.get("skill_subset") or []:
            if sk in skill_names:
                add_edge(nid, skill_id[sk], "uses", i=1)
                attribute(agent, sk, first.get("timestamp") or "", False)  # rung 5
        touch_agent(agent, first.get("timestamp") or "")
        add_edge(f"agent-{slugify(agent)}", nid, "launched", e=1, agent=agent)

    # ---- proposals ---------------------------------------------------------
    proposals = collapse_by_id(load_jsonl(PROPOSALS), "proposal_id")
    proposal_id_map: dict[str, str] = {}
    for pid, hist in proposals.items():
        first, latest = hist[0], hist[-1]
        nid = slugify(f"proposal-{pid}")
        proposal_id_map[pid] = nid
        d = date_of(first.get("timestamp"))
        verdict = latest.get("verdict") or "open"
        add_node(nid, "proposal", pid, date=d)
        add_card(nid, f"{pid} — {first.get('title', '')}", d,
                 f"{verdict} · {first.get('target_type', '?')}:{first.get('target', '?')}"
                 f" — {first.get('change', '')}",
                 "memory/brain/proposals.jsonl")
        filer = map_agent(first.get("agent_id"), "claude-code-main")
        touch_agent(filer, first.get("timestamp") or "")
        add_edge(f"agent-{slugify(filer)}", nid, "filed", e=1, agent=filer)
        if (first.get("target_type") or "").strip() == "skill":
            target = (first.get("target") or "").strip()
            if target in skill_names:
                add_edge(nid, skill_id[target], "targets", e=1)

    # ---- rules -------------------------------------------------------------
    rules = load_rules()
    rule_id_map: dict[str, str] = {}
    for r in rules:
        nid = slugify(f"rule-{r['rule_id']}")
        rule_id_map[r["rule_id"]] = nid
        add_node(nid, "rule", r["rule_id"], date=r.get("date") or None)
        imp = re.search(r"\*\*Imperative:\*\*\s*(.+?)(?:\n-\s\*\*|\Z)", r["body"], re.DOTALL)
        add_card(nid, f"{r['rule_id']} — {r['title']}", r.get("date") or "",
                 " ".join(imp.group(1).split()) if imp else r["title"],
                 "memory/brain/rules.md")
        m = EXTENDS_RE.search(r.get("body", ""))
        if m and m.group(1) in skill_names:
            add_edge(nid, skill_id[m.group(1)], "extends", e=1)

    # proposal → references → rule (rule_cited on the deciding row)
    for pid, hist in proposals.items():
        cited = hist[-1].get("rule_cited")
        if cited and cited in rule_id_map:
            add_edge(proposal_id_map[pid], rule_id_map[cited], "references", e=1)

    # ---- harvest findings --------------------------------------------------
    finding_by_hid: dict[str, str] = {}
    for f in feedback_rows:
        hid = f["harvest_id"]
        nid = slugify(f"harvest-{hid}-l{f.get('_source_line', 0)}")
        finding_by_hid.setdefault(hid, nid)
        d = f.get("date") or ""
        add_node(nid, "harvest_finding", f"{hid}:{f.get('class', '?')}", date=d)
        add_card(nid, f"{hid} — {f.get('skill', '')}:{f.get('class', '')}", d,
                 f"{f.get('ref', '')} — {f.get('evidence', '')}",
                 "memory/feedback.jsonl")
        sk = (f.get("skill") or "").strip()
        if sk in skill_names:
            add_edge(nid, skill_id[sk], "about", e=1)

    # finding → becomes → proposal (references carrying feedback.jsonl:HXXX)
    for pid, hist in proposals.items():
        for ref in hist[0].get("references") or []:
            if isinstance(ref, str) and ref.startswith("feedback.jsonl:"):
                hid = ref.split(":", 1)[1]
                if hid in finding_by_hid:
                    add_edge(finding_by_hid[hid], proposal_id_map[pid], "becomes", e=1)

    # ---- decisions / corrections -------------------------------------------
    fw_dec = load_decisions(FW_DECISIONS, "framework")
    ap_dec = (load_decisions(consumer / "DECISIONS.md", "apparatus")
              if consumer is not None else [])
    dec_by_slug = {d["slug"]: d for d in fw_dec + ap_dec}
    dec_by_head: dict[str, dict] = {}
    for d in fw_dec + ap_dec:
        dec_by_head.setdefault(d["head"], d)

    def ensure_decision_node(d: dict) -> str:
        nid = d["slug"]
        if nid not in nodes:
            add_node(nid, d["type"], d["head"], date=d.get("date") or None)
            add_card(nid, f"{d['head']} — {d['title']}", d.get("date") or "",
                     d["body"],
                     ("memory/DECISIONS.md" if d["side"] == "framework"
                      else "a_bgt_rsi/DECISIONS.md"))
            author = ("claude-code-main" if d["side"] == "framework"
                      else "human:decross1")
            touch_agent(author, (d.get("date") or "") + "T00:00:00Z")
            add_edge(f"agent-{slugify(author)}", nid, "authored", e=1, agent=author)
        return nid

    # corrections are first-class — always on the map
    for d in fw_dec + ap_dec:
        if d["type"] == "correction":
            nid = ensure_decision_node(d)
            # correction → enacts → rule (source-decision date + title match)
            for r in rules:
                if (r.get("date") == d.get("date")
                        and r["title"].strip().lower() == d["title"].strip().lower()):
                    add_edge(nid, rule_id_map[r["rule_id"]], "enacts", e=1)

    # proposal → produces → decision (decision_id), plus reference resolution
    for pid, hist in proposals.items():
        latest = hist[-1]
        dec_id = latest.get("decision_id")
        if dec_id and dec_id in dec_by_head:
            nid = ensure_decision_node(dec_by_head[dec_id])
            add_edge(proposal_id_map[pid], nid, "produces", e=1)
        for ref in hist[0].get("references") or []:
            if not isinstance(ref, str):
                continue
            if ref in dec_by_slug:                       # full decision slug
                nid = ensure_decision_node(dec_by_slug[ref])
                add_edge(proposal_id_map[pid], nid, "references", e=1)
            elif DECISION_HEAD_RE.match(ref) and ref in dec_by_head:
                nid = ensure_decision_node(dec_by_head[ref])
                add_edge(proposal_id_map[pid], nid, "references", e=1)
            elif ref in skill_names:                     # bare skill name
                add_edge(proposal_id_map[pid], skill_id[ref], "references", e=1)
            elif slugify(f"spawn-{ref}") in nodes:       # spawn id (SP-002)
                add_edge(proposal_id_map[pid], slugify(f"spawn-{ref}"), "references", e=1)

    # ---- narrative corrections + anomalies ----------------------------------
    for n in load_jsonl(NARRATIVES):
        if n.get("type") == "apparatus_event":
            continue
        kind = n.get("_type_override")
        if kind not in ("correction", "anomaly"):
            continue
        nid = narrative_slug(n)
        d = date_of(n.get("timestamp"))
        add_node(nid, kind, n.get("_title") or nid, date=d)
        add_card(nid, n.get("_title") or nid, d,
                 n.get("observed") or n.get("intent") or "",
                 "memory/brain/narratives.jsonl")
        author = map_agent(n.get("agent_id"), "claude-code-main")
        touch_agent(author, n.get("timestamp") or "")
        add_edge(f"agent-{slugify(author)}", nid, "authored", e=1, agent=author)

    # ---- typed edges.jsonl rows between governance entities -----------------
    for e in load_jsonl(EDGES):
        src, dst = e.get("src"), e.get("dst")
        if not src or not dst:
            continue
        if src in dec_by_slug and src not in nodes and dst in nodes:
            ensure_decision_node(dec_by_slug[src])
        if dst in dec_by_slug and dst not in nodes and src in nodes:
            ensure_decision_node(dec_by_slug[dst])
        if src in nodes and dst in nodes:
            add_edge(src, dst, e.get("type") or "linked_to", e=1)

    # ---- human gate activity (agent presence only) ---------------------------
    if consumer is not None:
        for r in load_jsonl(consumer / "memory" / "loop_feedback.jsonl"):
            who = f"human:{r.get('gated_by', 'unknown')}"
            touch_agent(who, r.get("gated_at") or "")

    # ---- agent nodes + used edges -------------------------------------------
    for agent, rec in sorted(agent_seen.items()):
        nid = f"agent-{slugify(agent)}"
        first = date_of(rec["first"]) if rec["first"] != "9999" else ""
        add_node(nid, "agent", agent, date=first or None)
        add_card(nid, agent, first,
                 f"{rec['rows']} ledger rows · first seen {first or '?'} · "
                 f"last {date_of(rec['last']) or '?'}",
                 "run logs + ledgers (attribution ladder)")
    for (agent, skill), c in sorted(cells.items()):
        add_edge(f"agent-{slugify(agent)}", skill_id[skill], "used",
                 e=c["e"], i=c["i"], agent=agent)

    # ---- prune + dedupe ------------------------------------------------------
    merged: dict[tuple[str, str, str], dict] = {}
    for e in edges:
        if e["src"] not in nodes or e["dst"] not in nodes:
            continue
        key = (e["src"], e["dst"], e["type"])
        if key in merged:
            m = merged[key]
            m["weight_e"] = m.get("weight_e", 0) + e.get("weight_e", 0)
            m["weight_i"] = m.get("weight_i", 0) + e.get("weight_i", 0)
            for k in ("weight_e", "weight_i"):
                if not m.get(k):
                    m.pop(k, None)
        else:
            merged[key] = dict(e)
    edge_list = [merged[k] for k in sorted(merged)]
    node_list = [nodes[k] for k in sorted(nodes, key=lambda i: (nodes[i]["type"], i))]
    card_map = {nid: cards[nid] for nid in sorted(cards) if nid in nodes}

    generated_at = datetime.now(timezone.utc).replace(microsecond=0) \
        .isoformat().replace("+00:00", "Z")
    return {"generated_at": generated_at, "nodes": node_list,
            "edges": edge_list, "cards": card_map}


# ---------------------------------------------------------------------------
# Emit (compare-before-write, generated_at excluded)
# ---------------------------------------------------------------------------

def parse_map_js(text: str) -> dict | None:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None


def emit(payload: dict) -> bool:
    OUT_JS.parent.mkdir(parents=True, exist_ok=True)
    if OUT_JS.exists():
        old = parse_map_js(OUT_JS.read_text())
        if old is not None:
            a, b = dict(old), dict(payload)
            a["generated_at"] = b["generated_at"] = None
            if a == b:
                return False
    OUT_JS.write_text(
        "// auto-generated by scripts/project_map.py — do not edit\n"
        "window.BRAIN_MAP = " + json.dumps(payload, indent=1, ensure_ascii=False)
        + ";\n")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Project the governance graph to map_data.js (window.BRAIN_MAP).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the rollup; write nothing.")
    args = parser.parse_args()

    payload = build_map()
    bad = [n for n in payload["nodes"] if n["type"] in EXCLUDED_TYPES]
    if bad:
        print(f"ERROR: {len(bad)} excluded-type nodes leaked: "
              f"{sorted({n['type'] for n in bad})}", file=sys.stderr)
        return 1
    if len(payload["nodes"]) > MAX_NODES:
        print(f"ERROR: {len(payload['nodes'])} nodes > cap {MAX_NODES}", file=sys.stderr)
        return 1
    blob = json.dumps(payload, indent=1, ensure_ascii=False)
    if len(blob) >= MAX_BYTES:
        print(f"ERROR: payload {len(blob)} B ≥ cap {MAX_BYTES} B", file=sys.stderr)
        return 1

    by_type = defaultdict(int)
    for n in payload["nodes"]:
        by_type[n["type"]] += 1
    by_edge = defaultdict(int)
    for e in payload["edges"]:
        by_edge[e["type"]] += 1
    print("map v1 — governance graph projection")
    print(f"  consumer: {resolve_consumer()}")
    print(f"  nodes: {len(payload['nodes'])}  "
          + "  ".join(f"{t}={c}" for t, c in sorted(by_type.items())))
    print(f"  edges: {len(payload['edges'])}  "
          + "  ".join(f"{t}={c}" for t, c in sorted(by_edge.items())))
    print(f"  cards: {len(payload['cards'])}  bytes: {len(blob)}")
    if args.dry_run:
        print("DRY RUN — nothing written.")
        return 0
    changed = emit(payload)
    print(f"  {'wrote' if changed else 'unchanged'} {OUT_JS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
