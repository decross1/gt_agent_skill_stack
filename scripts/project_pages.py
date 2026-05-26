#!/usr/bin/env python3
"""project_pages.py — project brain entities into markdown pages + a slim index.

Reads `narratives.jsonl` + `edges.jsonl` + framework/apparatus `DECISIONS.md`
and emits one markdown page per entity to `memory/brain/pages/<slug>.md`,
plus `memory/brain/view/index.json` for the graph visualizer.

Pages are derived views; the JSONL files remain canonical. Deterministic and
idempotent: re-running with the same inputs produces the same outputs.

Slug conventions:
  - reflection           → `<task_id>` (sanitized)
  - apparatus_event      → `apparatus-<file_stem>-L<line>`
  - decision (framework) → `dec-fw-<head-slug>` (head = "YYYY-MM-DD" or "D-NNN")
  - decision (apparatus) → `dec-ap-<head-slug>`
  - hand-authored        → as written in `_slug` field of a narrative entry
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CONSUMER = REPO.parent / "a_bgt_rsi"

NARRATIVES = REPO / "memory" / "brain" / "narratives.jsonl"
EDGES = REPO / "memory" / "brain" / "edges.jsonl"
PROPOSALS = REPO / "memory" / "brain" / "proposals.jsonl"
PAGES = REPO / "memory" / "brain" / "pages"
INDEX = REPO / "memory" / "brain" / "view" / "index.json"
GRAPH_DATA = REPO / "memory" / "brain" / "view" / "graph_data.js"
FW_DECISIONS = REPO / "memory" / "DECISIONS.md"
AP_DECISIONS = CONSUMER / "DECISIONS.md"
FEEDBACK = REPO / "memory" / "feedback.jsonl"
RULES_MD = REPO / "memory" / "brain" / "rules.md"

# Apparatus files read directly for stage synthesis (read-only — brain firewall).
# loop_memory.jsonl moved from run_state/ to memory/ at some point; try both.
CONSUMER_LOOP_MEMORY_CANDIDATES = (
    CONSUMER / "memory" / "loop_memory.jsonl",
    CONSUMER / "run_state" / "loop_memory.jsonl",
)
CONSUMER_WEEK1_RUN = CONSUMER / "run_state" / "week1.run.jsonl"
CONSUMER_CALLS = CONSUMER / "logs" / "calls.jsonl"

DECISION_HEADER_RE = re.compile(
    r"^##\s+(?P<head>(?P<date>\d{4}-\d{2}-\d{2})|D-\d+)\s*[—–-]\s*(?P<title>[^\n]+)$",
    re.MULTILINE,
)

SAFE_SLUG = re.compile(r"[^a-z0-9]+")


def slugify(s: str) -> str:
    s = s.lower().strip()
    s = SAFE_SLUG.sub("-", s)
    return s.strip("-") or "unnamed"


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    with path.open() as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"warn: {path.name}:{lineno} malformed JSON: {e}", file=sys.stderr)
                continue
            obj["_source_line"] = lineno
            out.append(obj)
    return out


def narrative_slug(n: dict) -> str:
    if n.get("_slug"):
        return n["_slug"]
    if n.get("type") == "apparatus_event":
        src = n.get("_source", {})
        return f"apparatus-{Path(src.get('file', 'unknown')).stem}-l{src.get('line', 0)}"
    tid = n.get("task_id") or "untitled"
    return slugify(tid)


def decision_slug(head: str, side: str, title: str = "") -> str:
    prefix = "dec-fw" if side == "framework" else "dec-ap"
    head_slug = slugify(head)
    if title:
        title_slug = slugify(" ".join(title.split()[:5]))[:48]
        if title_slug:
            return f"{prefix}-{head_slug}-{title_slug}"
    return f"{prefix}-{head_slug}"


def load_decisions(path: Path, side: str) -> list[dict]:
    if not path.exists():
        return []
    text = path.read_text()
    headers = list(DECISION_HEADER_RE.finditer(text))
    out = []
    for i, m in enumerate(headers):
        start = m.end()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        body = text[start:end].strip()
        date_in_body = re.search(r"(\d{4}-\d{2}-\d{2})", body[:400])
        date = m.group("date") or (date_in_body.group(1) if date_in_body else "")
        head = m.group("head")
        title = m.group("title").strip()
        is_correction = bool(re.search(r"^\*\*Correction:?\*\*", body, re.MULTILINE))
        out.append({
            "slug": decision_slug(head, side, title),
            "type": "correction" if is_correction else "decision",
            "side": side,
            "head": head,
            "title": title,
            "date": date,
            "body": body,
        })
    return out


def render_page(entity: dict, outgoing: list[dict], incoming: list[dict]) -> str:
    fm = {
        "slug": entity["slug"],
        "type": entity["type"],
        "date": entity.get("date", ""),
        "source": entity.get("source", ""),
    }
    lines: list[str] = ["---"]
    for k, v in fm.items():
        if v:
            lines.append(f"{k}: {json.dumps(v)}")
    if outgoing:
        lines.append("edges:")
        for e in outgoing:
            lines.append(f"  - {{type: {e['type']}, dst: {json.dumps(e['dst'])}, dst_type: {json.dumps(e.get('dst_type', ''))}}}")
    lines.append("---")
    lines.append("")
    lines.append(f"# {entity.get('title') or entity['slug']}")
    lines.append("")
    if entity.get("subtitle"):
        lines.append(f"_{entity['subtitle']}_")
        lines.append("")
    body = entity.get("body", "").strip()
    if body:
        lines.append(body)
        lines.append("")
    if outgoing:
        lines.append("## Links")
        lines.append("")
        for e in outgoing:
            lines.append(f"- **{e['type']}** → `{e['dst']}` ({e.get('dst_type', '?')})")
        lines.append("")
    if incoming:
        lines.append("## Referenced by")
        lines.append("")
        for e in incoming:
            lines.append(f"- `{e['src']}` ({e.get('src_type', '?')}) — **{e['type']}**")
        lines.append("")
    return "\n".join(lines)


# Apparatus narratives all carry `type: apparatus_event` in the JSONL — that
# is the brain's narrative-type field and we don't rewrite it. But for the
# graph view, we want finer visual separation between an iteration record,
# the orchestrator events it produced, and the vLLM wrapper calls those
# events triggered. We derive a sub-kind here, override `entity.type` with
# it so graph.html can color the nodes distinctly, and surface a human
# display label for the sidebar title.
def kind_from_narrative(n: dict) -> tuple[str, str]:
    """Return (kind, display_agent) for an apparatus_event narrative.

    Kinds:
      iteration          — LOOP_V0 iteration record (one per research iteration)
      orchestrator_event — Nara's loop_v0_* events (tool_dispatch/receipt, start/complete)
      llm_call           — a vLLM wrapper call (one per request_id)
      apparatus_event    — catch-all fallback for unrecognized apparatus shapes
    """
    agent_id = (n.get("agent_id") or "").strip()
    src_file = (n.get("_source") or {}).get("file", "")
    consumer = "a_bgt_rsi"

    if src_file == "loop_memory.jsonl" or agent_id == "nara":
        return ("iteration", f"{consumer}: Nara")
    if src_file == "week1.run.jsonl" or agent_id.startswith("nara:") or agent_id.startswith("orchestrator:"):
        return ("orchestrator_event", f"{consumer}: Nara/Orchestrator")
    if src_file == "calls.jsonl":
        return ("llm_call", f"{consumer}: Nara/LLM")
    if "critic" in src_file:
        return ("llm_call", f"{consumer}: Critic")
    return ("apparatus_event", agent_id or "apparatus")


def entity_from_narrative(n: dict) -> dict:
    slug = narrative_slug(n)
    if n.get("type") == "apparatus_event":
        src = n.get("_source", {})
        kind, display_agent = kind_from_narrative(n)
        title = f"{display_agent} — {Path(src.get('file', '?')).stem} L{src.get('line', 0)}"
        subtitle = n.get("intent", "")
        body = "\n\n".join([
            f"**Did:** {n.get('did', '')}",
            f"**Observed:** {n.get('observed', '')}",
        ])
        date = (n.get("timestamp") or "")[:10]
        return {
            "slug": slug,
            "type": kind,
            "date": date,
            "title": title,
            "subtitle": subtitle,
            "body": body,
            "source": f"{src.get('file','?')}:{src.get('line','?')}",
        }
    # reflection or hand-authored entity
    title = n.get("_title") or n.get("task_id") or slug
    typ = n.get("_type_override") or "reflection"
    body_parts = []
    for label, key in [("Intent", "intent"), ("Did", "did"), ("Observed", "observed"),
                       ("Would do differently", "would_do_differently")]:
        v = (n.get(key) or "").strip()
        if v:
            body_parts.append(f"**{label}:** {v}")
    if n.get("corrections_honored"):
        body_parts.append(f"**Corrections honored:** {', '.join(n['corrections_honored'])}")
    return {
        "slug": slug,
        "type": typ,
        "date": (n.get("timestamp") or "")[:10],
        "title": title,
        "subtitle": n.get("_subtitle"),
        "body": "\n\n".join(body_parts),
        "source": "memory/brain/narratives.jsonl",
    }


# ---------------------------------------------------------------------------
# Stage synthesis — collapse each (iteration, tool) dispatch+receipt+call triple
# into one `stage` node so the default Research view shows a clean per-iteration
# pipeline (Hypothesize → Retrieve → Novelty → Critique → Journal) instead of
# 13+ mechanical nodes per iteration. The mechanical nodes still exist as
# apparatus_event narratives — stages reference them via derived_from edges
# so the trace is walkable when Mechanics view is enabled.
#
# Reads apparatus JSONL files directly (read-only — brain firewall preserved).
# Synthetic edges live in graph_data.js only; never written to edges.jsonl.
# ---------------------------------------------------------------------------

# Friendly names for LOOP_V0 tool-calls (workers). Lookup is non-exhaustive;
# tools not listed fall back to title-cased identifier.
_WORKER_PRETTY = {
    "hypothesize": "Hypothesize",
    "retrieve_literature": "Retrieve",
    "query_chroma": "Retrieve",          # LOOP_V0 Part 1 alias
    "summarize_paper": "Summarize",
    "play_pd_match": "PD Match",
    "novelty_classify": "Novelty",
    "critic_loop_v0": "Critique",
    "journal_writer": "Journal",
    "journal_writer_stub": "Journal",    # LOOP_V0 Part 1 alias
}


def worker_pretty(tool: str) -> str:
    if tool in _WORKER_PRETTY:
        return _WORKER_PRETTY[tool]
    return tool.replace("_", " ").title()


def load_iteration_records() -> list[dict]:
    """Read loop_memory.jsonl from whichever candidate path exists."""
    for p in CONSUMER_LOOP_MEMORY_CANDIDATES:
        if p.exists():
            return load_jsonl(p)
    return []


def load_loop_v0_events() -> list[dict]:
    """LOOP_V0 events from week1.run.jsonl (with `_lineno` for slug parity with ingest)."""
    if not CONSUMER_WEEK1_RUN.exists():
        return []
    out = []
    with CONSUMER_WEEK1_RUN.open() as f:
        for lineno, raw in enumerate(f, 1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                o = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not (isinstance(o.get("event_type"), str) and o["event_type"].startswith("loop_v0_")):
                continue
            o["_lineno"] = lineno
            out.append(o)
    return out


def load_calls_index() -> dict[str, str]:
    """request_id -> slug of the apparatus_event narrative for that vLLM call."""
    idx: dict[str, str] = {}
    if not CONSUMER_CALLS.exists():
        return idx
    with CONSUMER_CALLS.open() as f:
        for lineno, raw in enumerate(f, 1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                o = json.loads(raw)
            except json.JSONDecodeError:
                continue
            rid = o.get("request_id")
            if rid:
                # mirrors narrative_slug() for apparatus_event from calls.jsonl
                idx[rid] = slugify(f"apparatus-{Path(CONSUMER_CALLS.name).stem}-l{lineno}")
    return idx


def synthesize_stages() -> tuple[list[dict], list[dict]]:
    """Build stage entities + synthetic edges from apparatus JSONL.

    For each iteration in loop_memory.jsonl, group its LOOP_V0 events by tool
    (dispatch + receipt pairs) and synthesize one `stage` entity per tool call,
    in the order it appeared in `tool_calls_made`.

    Edges:
      - iteration --produced--> stage
      - stage --derived_from--> triggering vLLM call (via parent_request_id)
      - stage --derived_from--> dispatch event + receipt event

    Returns (entities, edges). Edges are synthetic — not appended to edges.jsonl.
    """
    iterations = load_iteration_records()
    events = load_loop_v0_events()
    calls_index = load_calls_index()

    # Group events by (iteration_id, tool); track which iterations had a fallback.
    by_iter_tool: dict[tuple[str, str], list[dict]] = defaultdict(list)
    fallback_iters: set[str] = set()
    for ev in events:
        iid = ev.get("iteration_id", "")
        if ev.get("event_type") == "loop_v0_fallback":
            fallback_iters.add(iid)
            continue
        tool = ev.get("tool")
        if tool:
            by_iter_tool[(iid, tool)].append(ev)

    entities: list[dict] = []
    edges: list[dict] = []

    for it in iterations:
        iid = it.get("iteration_id", "")
        if not iid:
            continue
        iter_slug = slugify(iid)
        tools = it.get("tool_calls_made") or []
        narration_log = it.get("narration_log") or []
        # First narration entry per tool (the assistant's prose before invoking it).
        narr_by_tool: dict[str, str] = {}
        for ne in narration_log:
            t = ne.get("tool")
            if t and t not in narr_by_tool:
                narr_by_tool[t] = (ne.get("text") or "").strip()

        # Count occurrences of each tool to disambiguate slugs if a tool is called twice.
        tool_seen_count: dict[str, int] = defaultdict(int)
        for i, tool in enumerate(tools, start=1):
            tool_seen_count[tool] += 1
            occurrence = tool_seen_count[tool]
            tool_events = by_iter_tool.get((iid, tool), [])
            dispatch = next((e for e in tool_events if e.get("event_type") == "loop_v0_tool_dispatch"), None)
            receipt = next((e for e in tool_events if e.get("event_type") == "loop_v0_tool_receipt"), None)
            status = (receipt or {}).get("status") or "—"
            parent_rid = (dispatch or {}).get("parent_request_id") or (receipt or {}).get("parent_request_id")
            ts = (dispatch or receipt or {}).get("timestamp", "")
            date = ts[:10] if ts else (it.get("started_at") or "")[:10]
            narr_text = narr_by_tool.get(tool, "")

            stage_slug = slugify(f"stage-{iid}-{tool}-{occurrence}")
            pretty = worker_pretty(tool)

            # Build sidebar body.
            body_parts = [
                f"**Step {i} of {len(tools)}** — tool `{tool}` ({pretty})",
                f"**Status:** {status}",
            ]
            if iid in fallback_iters and i == len(tools):
                # A loop_v0_fallback event in an iteration most plausibly maps to the
                # last stage (the one whose receipt errored). Mark it visibly.
                body_parts.append("⚠️ **Fallback fired** — primary path failed; recovery path ran.")
            if narr_text:
                trimmed = narr_text[:500] + ("…" if len(narr_text) > 500 else "")
                body_parts.append(f"**Reasoning (Nara's prose before this step):**\n\n{trimmed}")
            if parent_rid:
                body_parts.append(f"**Triggered by call:** `{parent_rid[:8]}…`")

            entities.append({
                "slug": stage_slug,
                "type": "stage",
                "worker": tool,           # raw worker name — graph.html colors stages by this
                "step": i,
                "date": date,
                "title": f"{pretty} — {iid} (step {i})",
                "subtitle": f"worker: {tool}",
                "body": "\n\n".join(body_parts),
                "source": f"loop_memory.jsonl + week1.run.jsonl",
            })

            # iteration → produced → stage (visible in Research view)
            edges.append({
                "timestamp": ts,
                "src": iter_slug,
                "src_type": "iteration",
                "type": "produced",
                "dst": stage_slug,
                "dst_type": "stage",
                "source_event": iid,
                "agent_id": "project_pages:synthesize_stages",
            })
            # stage → derived_from → triggering call (Mechanics view debug path)
            if parent_rid and parent_rid in calls_index:
                edges.append({
                    "timestamp": ts,
                    "src": stage_slug,
                    "src_type": "stage",
                    "type": "derived_from",
                    "dst": calls_index[parent_rid],
                    "dst_type": "apparatus_event",
                    "source_event": iid,
                    "agent_id": "project_pages:synthesize_stages",
                })
            # stage → derived_from → dispatch/receipt event nodes
            for ev in tool_events:
                ev_slug = slugify(
                    f"event-{iid}-{ev.get('event_type','')}-{tool}-l{ev['_lineno']}"
                )
                edges.append({
                    "timestamp": ev.get("timestamp", ts),
                    "src": stage_slug,
                    "src_type": "stage",
                    "type": "derived_from",
                    "dst": ev_slug,
                    "dst_type": "apparatus_event",
                    "source_event": iid,
                    "agent_id": "project_pages:synthesize_stages",
                })

    return entities, edges


# ---------------------------------------------------------------------------
# Loop projection — promote harvest findings, proposals, and active rules to
# first-class graph nodes. Edges synthesized here close P-006: the
# harvest_finding → proposal → decision → rule chain is now traversable.
#
# Synthetic edges live in graph_data.js only — edges.jsonl stays canonical.
# ---------------------------------------------------------------------------

RULE_HEADER_RE = re.compile(r"^###\s+(?P<id>FR-\d+|AR-\d+)\s+—\s+(?P<title>[^\n]+)$", re.MULTILINE)
RULE_SOURCE_RE = re.compile(r"^- \*\*Source decision:\*\*\s+`(?P<date>\d{4}-\d{2}-\d{2})`", re.MULTILINE)


def load_rules() -> list[dict]:
    """Parse rules.md into one record per active rule."""
    if not RULES_MD.exists():
        return []
    text = RULES_MD.read_text()
    headers = list(RULE_HEADER_RE.finditer(text))
    out = []
    for i, m in enumerate(headers):
        start = m.end()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        body = text[start:end].strip()
        rule_id = m.group("id")
        title = m.group("title").strip()
        date_m = RULE_SOURCE_RE.search(body)
        date = date_m.group("date") if date_m else ""
        side = "framework" if rule_id.startswith("FR-") else "apparatus"
        out.append({
            "rule_id": rule_id,
            "title": title,
            "body": body,
            "date": date,
            "side": side,
        })
    return out


def synthesize_loop_entities(
    fw_dec: list[dict],
    ap_dec: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Project harvest findings, proposals, and rules; synthesize their edges.

    Returns (entities, edges). Edges are synthetic — not appended to edges.jsonl.

    Edge model:
      - harvest_finding --becomes--> proposal      (proposal.references cites feedback.jsonl:HXXX)
      - proposal --produces--> decision            (proposal.decision_id set)
      - proposal --auto_rejected_by--> rule        (verdict=auto-reject, rule_cited set)
      - decision --enacts--> rule                  (rule.Source decision date matches a decision's date+correction flag)
    """
    entities: list[dict] = []
    edges: list[dict] = []

    # --- harvest findings -------------------------------------------------
    feedback_rows = load_jsonl(FEEDBACK)
    finding_slug_by_hid: dict[str, str] = {}
    for f in feedback_rows:
        hid = f.get("harvest_id")
        if not hid:
            continue
        # Each finding can appear multiple times (one per evidence line).
        # Slug by harvest_id + source line so duplicates don't collide.
        line = f.get("_source_line", 0)
        slug = slugify(f"harvest-{hid}-l{line}")
        # First occurrence per hid wins for the canonical edge target.
        finding_slug_by_hid.setdefault(hid, slug)
        ev = (f.get("evidence") or "").strip()
        plan_candidate = (f.get("plan_candidate") or "").strip()
        body_parts = [
            f"**Source skill:** `{f.get('skill','')}`",
            f"**Class:** {f.get('class','')}",
            f"**Ref:** {f.get('ref','')}",
            f"**Source project:** {f.get('source','')}",
            f"**Evidence:** {ev}",
        ]
        if plan_candidate:
            body_parts.append(f"**Plan candidate:** {plan_candidate}")
        entities.append({
            "slug": slug,
            "type": "harvest_finding",
            "date": f.get("date", ""),
            "title": f"{hid} — {f.get('skill','')}:{f.get('class','')}",
            "subtitle": f.get("ref", ""),
            "body": "\n\n".join(body_parts),
            "source": "memory/feedback.jsonl",
        })

    # --- proposals --------------------------------------------------------
    proposals = load_jsonl(PROPOSALS)
    # latest entry per proposal_id is the current view
    proposal_latest: dict[str, dict] = {}
    proposal_first: dict[str, dict] = {}
    for p in sorted(proposals, key=lambda r: r.get("timestamp", "")):
        pid = p.get("proposal_id")
        if not pid:
            continue
        proposal_first.setdefault(pid, p)
        proposal_latest[pid] = p

    proposal_slug_by_pid: dict[str, str] = {}
    for pid, latest in proposal_latest.items():
        first = proposal_first[pid]
        slug = slugify(f"proposal-{pid}")
        proposal_slug_by_pid[pid] = slug
        verdict = latest.get("verdict") or "open"
        body_parts = [
            f"**Verdict:** `{verdict}`",
            f"**Target:** {first.get('target_type','?')} → `{first.get('target','?')}`",
            f"**Change:** {first.get('change','')}",
            f"**Reasoning:** {first.get('reasoning','')}",
        ]
        if first.get("references"):
            body_parts.append(
                "**References:** " + ", ".join(f"`{r}`" for r in first["references"])
            )
        if latest.get("rule_cited"):
            body_parts.append(f"**Rule cited:** `{latest['rule_cited']}`")
        if latest.get("verdict_reasoning"):
            body_parts.append(f"**Verdict reasoning:** {latest['verdict_reasoning']}")
        if latest.get("decision_id"):
            body_parts.append(f"**Decision id:** `{latest['decision_id']}`")
        entities.append({
            "slug": slug,
            "type": "proposal",
            "date": (first.get("timestamp") or "")[:10],
            "title": f"{pid} — {first.get('title','')}",
            "subtitle": f"agent: {first.get('agent_id','')}",
            "body": "\n\n".join(body_parts),
            "source": "memory/brain/proposals.jsonl",
        })

        # harvest_finding -becomes-> proposal
        for ref in first.get("references") or []:
            if not isinstance(ref, str):
                continue
            if ref.startswith("feedback.jsonl:"):
                hid = ref.split(":", 1)[1]
                src_slug = finding_slug_by_hid.get(hid)
                if src_slug:
                    edges.append({
                        "timestamp": first.get("timestamp", ""),
                        "src": src_slug,
                        "src_type": "harvest_finding",
                        "type": "becomes",
                        "dst": slug,
                        "dst_type": "proposal",
                        "source_event": f"loop_chain:{pid}",
                        "agent_id": "project_pages:synthesize_loop_entities",
                    })

        # proposal -produces-> decision
        dec_id = latest.get("decision_id")
        if dec_id:
            # decision_id may be a date "2026-05-24" or a "D-NNN" form; both
            # were used as the head in DECISION_HEADER_RE. Find the matching
            # decision slug by scanning fw_dec + ap_dec for that head.
            for d in fw_dec + ap_dec:
                if d.get("head") == dec_id:
                    edges.append({
                        "timestamp": latest.get("timestamp", ""),
                        "src": slug,
                        "src_type": "proposal",
                        "type": "produces",
                        "dst": d["slug"],
                        "dst_type": d["type"],  # decision or correction
                        "source_event": f"loop_chain:{pid}",
                        "agent_id": "project_pages:synthesize_loop_entities",
                    })

    # --- rules ------------------------------------------------------------
    rules = load_rules()
    rule_slug_by_id: dict[str, str] = {}
    for r in rules:
        slug = slugify(f"rule-{r['rule_id']}")
        rule_slug_by_id[r["rule_id"]] = slug
        entities.append({
            "slug": slug,
            "type": "rule",
            "date": r["date"],
            "title": f"{r['rule_id']} — {r['title']}",
            "subtitle": f"{r['side']} active rule",
            "body": r["body"],
            "source": "memory/brain/rules.md (derived from DECISIONS.md)",
        })

        # decision -enacts-> rule. Match by date AND title — multiple
        # correction-flagged decisions can share a date, so date alone fans
        # out into a cartesian product. The rule's title comes verbatim from
        # the source decision's header in DECISIONS.md.
        if r["date"]:
            pool = fw_dec if r["side"] == "framework" else ap_dec
            r_title_norm = r["title"].strip().lower()
            for d in pool:
                if (d.get("date") == r["date"]
                        and d.get("type") == "correction"
                        and d.get("title", "").strip().lower() == r_title_norm):
                    edges.append({
                        "timestamp": r["date"] + "T00:00:00Z",
                        "src": d["slug"],
                        "src_type": "correction",
                        "type": "enacts",
                        "dst": slug,
                        "dst_type": "rule",
                        "source_event": f"loop_chain:rule:{r['rule_id']}",
                        "agent_id": "project_pages:synthesize_loop_entities",
                    })

    # --- proposal -auto_rejected_by-> rule -------------------------------
    for pid, latest in proposal_latest.items():
        if latest.get("verdict") != "auto-reject":
            continue
        cited = latest.get("rule_cited")
        if not cited:
            continue
        rule_slug = rule_slug_by_id.get(cited)
        if not rule_slug:
            continue
        edges.append({
            "timestamp": latest.get("timestamp", ""),
            "src": proposal_slug_by_pid[pid],
            "src_type": "proposal",
            "type": "auto_rejected_by",
            "dst": rule_slug,
            "dst_type": "rule",
            "source_event": f"loop_chain:{pid}",
            "agent_id": "project_pages:synthesize_loop_entities",
        })

    return entities, edges


def entity_from_decision(d: dict) -> dict:
    return {
        "slug": d["slug"],
        "type": d["type"],
        "date": d["date"],
        "title": f"{d['head']} — {d['title']}",
        "subtitle": f"{'apparatus' if d['side'] == 'apparatus' else 'framework'} decision",
        "body": d["body"],
        "source": ("memory/DECISIONS.md" if d["side"] == "framework" else "a_bgt_rsi/DECISIONS.md"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Project brain entities to pages + index.")
    parser.add_argument(
        "--apparatus-pages-cap",
        type=int,
        default=200,
        help="Cap on apparatus_event pages emitted (default 200, to keep pages/ scannable; the canonical data is still in narratives.jsonl).",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    PAGES.mkdir(parents=True, exist_ok=True)
    INDEX.parent.mkdir(parents=True, exist_ok=True)

    narratives = load_jsonl(NARRATIVES)
    edges = load_jsonl(EDGES)
    fw_dec = load_decisions(FW_DECISIONS, "framework")
    ap_dec = load_decisions(AP_DECISIONS, "apparatus")

    # Build entity list.
    # Apparatus events are FIFO-capped to keep pages/ scannable. Newer matters
    # more than older for daily use — sort apparatus narratives by timestamp
    # descending and take the first N. Non-apparatus narratives all get pages.
    entities: dict[str, dict] = {}
    apparatus_narrs = [n for n in narratives if n.get("type") == "apparatus_event"]
    apparatus_narrs.sort(key=lambda n: n.get("timestamp", ""), reverse=True)
    apparatus_kept = apparatus_narrs[:args.apparatus_pages_cap]
    kept_apparatus_lines = {(n.get("_source", {}).get("file"), n.get("_source", {}).get("line"))
                            for n in apparatus_kept}
    for n in narratives:
        if n.get("type") == "apparatus_event":
            src = n.get("_source", {})
            if (src.get("file"), src.get("line")) not in kept_apparatus_lines:
                continue
        e = entity_from_narrative(n)
        entities[e["slug"]] = e
    for d in fw_dec + ap_dec:
        e = entity_from_decision(d)
        entities[e["slug"]] = e

    # Synthesize per-tool stage entities from apparatus JSONL. Stages collapse
    # the dispatch+receipt+call triple per worker into one node so the default
    # Research view renders a clean per-iteration pipeline. Synthetic edges
    # live only in graph_data.js — edges.jsonl stays canonical (only narrate/
    # ingest-emitted edges).
    stage_entities, stage_edges = synthesize_stages()
    for e in stage_entities:
        entities[e["slug"]] = e

    # Synthesize loop entities — harvest_finding, proposal, rule — and the
    # edges that make harvest→propose→decide→rule traversable in the graph.
    loop_entities, loop_edges = synthesize_loop_entities(fw_dec, ap_dec)
    for e in loop_entities:
        entities[e["slug"]] = e

    # Suppress redundant iter -> {event, call} edges where a stage already
    # covers the destination. Otherwise the graph draws TWO arrows into each
    # mechanical node — one from the iteration root and one from the stage —
    # which looks like the call has two parents. The right model is hierarchy:
    # iter -> stage -> (event | call). iter -> {iteration_start, iteration_complete,
    # fallback} stays because those events are NOT covered by any stage.
    stage_covered_dsts = {
        e["dst"] for e in stage_edges
        if e.get("type") == "derived_from"
    }
    filtered_canonical = []
    suppressed = 0
    for e in edges:
        src = e.get("src", "")
        dst = e.get("dst", "")
        if (src.startswith("iter-")
                and e.get("type") == "produced"
                and dst in stage_covered_dsts):
            suppressed += 1
            continue
        filtered_canonical.append(e)
    edges = filtered_canonical + stage_edges + loop_edges

    # Group edges by src and dst.
    out_edges: dict[str, list[dict]] = defaultdict(list)
    in_edges: dict[str, list[dict]] = defaultdict(list)
    dangling: list[dict] = []
    for e in edges:
        src = e.get("src")
        dst = e.get("dst")
        if not src or not dst:
            dangling.append(e)
            continue
        out_edges[src].append(e)
        in_edges[dst].append(e)
        if src not in entities:
            dangling.append({**e, "_reason": "src not found"})
        if dst not in entities:
            dangling.append({**e, "_reason": "dst not found"})

    if args.dry_run:
        print(f"DRY RUN — would render {len(entities)} pages "
              f"({len(apparatus_narrs)} apparatus_event seen, cap={args.apparatus_pages_cap})")
        print(f"  edges: {len(edges)}  dangling: {len(dangling)}")
        return 0

    # Render pages.
    written = 0
    for slug, e in sorted(entities.items()):
        page = render_page(e, out_edges.get(slug, []), in_edges.get(slug, []))
        path = PAGES / f"{slug}.md"
        existing = path.read_text() if path.exists() else None
        if existing != page:
            path.write_text(page)
        written += 1

    # Sweep stale pages: any file in pages/ whose slug is not in the current
    # entity set is a leftover from a prior projection (e.g. after a slug
    # rename). Pages are derived; the JSONL is canonical, so it is safe to
    # remove. .gitkeep is exempt.
    swept = 0
    keep = set(entities.keys())
    for p in PAGES.glob("*.md"):
        if p.stem not in keep:
            p.unlink()
            swept += 1

    # Write slim index for the graph viewer. `worker` + `step` are populated for
    # stage entities only — graph.html uses `worker` to pick a per-worker color
    # from STAGE_COLORS so the 5-stage pipeline reads at a glance.
    index_records = [
        {
            "slug": e["slug"],
            "type": e["type"],
            "date": e.get("date", ""),
            "title": e.get("title", ""),
            **({"worker": e["worker"]} if "worker" in e else {}),
            **({"step": e["step"]} if "step" in e else {}),
        }
        for e in entities.values()
    ]
    index_records.sort(key=lambda r: (r["type"], r["slug"]))
    INDEX.write_text(json.dumps(index_records, indent=2) + "\n")

    # Slim graph_data.js for the static graph viewer (file://-loadable).
    graph_edges = [
        {
            "src": e.get("src", ""),
            "src_type": e.get("src_type", ""),
            "type": e.get("type", ""),
            "dst": e.get("dst", ""),
            "dst_type": e.get("dst_type", ""),
        }
        for e in edges
        if e.get("src") and e.get("dst")
    ]
    # Embed page contents so the graph viewer can render them via file://
    # (no fetch needed). Keep it slim — strip frontmatter, cap each page.
    page_contents: dict[str, str] = {}
    for slug in entities.keys():
        p = PAGES / f"{slug}.md"
        if p.exists():
            raw = p.read_text()
            # strip yaml frontmatter for in-panel display
            if raw.startswith("---"):
                end = raw.find("\n---", 3)
                if end != -1:
                    raw = raw[end + 4:].lstrip("\n")
            page_contents[slug] = raw[:6000]  # safety cap

    # Project proposals into the graph payload so the viewer can list them.
    proposals_raw = load_jsonl(PROPOSALS)
    # Build a current view: latest entry per proposal_id (supersedes-by-id).
    proposal_latest: dict[str, dict] = {}
    for p in proposals_raw:
        pid = p.get("proposal_id")
        if not pid:
            continue
        proposal_latest[pid] = p
    proposals_payload = sorted(proposal_latest.values(), key=lambda r: r.get("timestamp", ""))

    graph_payload = {
        "nodes": index_records,
        "edges": graph_edges,
        "pages": page_contents,
        "proposals": proposals_payload,
    }
    GRAPH_DATA.write_text(
        "// auto-generated by scripts/project_pages.py — do not edit\n"
        "window.BRAIN_GRAPH = " + json.dumps(graph_payload, indent=2) + ";\n"
    )

    print(f"projected {written} pages → {PAGES}  (swept {swept} stale)")
    print(f"  edges: {len(edges)}  dangling: {len(dangling)}  "
          f"suppressed: {suppressed} iter->{{event,call}} edges covered by stages")
    if dangling:
        for d in dangling[:5]:
            print(f"  dangling: src={d.get('src')} → dst={d.get('dst')}  ({d.get('_reason', 'no src/dst')})")
        if len(dangling) > 5:
            print(f"  ... and {len(dangling) - 5} more")
    print(f"index → {INDEX}  ({len(index_records)} entries)")
    print(f"graph_data → {GRAPH_DATA}  ({len(graph_edges)} edges, "
          f"{len(page_contents)} pages, {len(proposals_payload)} proposals)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
