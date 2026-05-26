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
              f"({apparatus_count} apparatus_event seen, cap={args.apparatus_pages_cap})")
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

    # Write slim index for the graph viewer.
    index_records = [
        {
            "slug": e["slug"],
            "type": e["type"],
            "date": e.get("date", ""),
            "title": e.get("title", ""),
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
    print(f"  edges: {len(edges)}  dangling: {len(dangling)}")
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
