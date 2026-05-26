#!/usr/bin/env python3
"""ingest_apparatus.py — project a_bgt_rsi apparatus logs into narratives + edges.

Reads JSONL from `a_bgt_rsi/logs/` (vLLM wrapper calls, orchestrator events)
and `a_bgt_rsi/run_state/` (LOOP_V0 iteration records + per-iteration events),
and appends:
  - one `apparatus_event` narrative per source line to `memory/brain/narratives.jsonl`
  - typed lineage edges (iteration→event, iteration→call, call→event) to
    `memory/brain/edges.jsonl`

Deterministic (no LLM); idempotent via `(source_file, source_line)` keys for
narratives and `(src, type, dst)` tuples for edges.

Recognized shapes:
  - LOOP_V0 iteration record (`loop_memory.jsonl`):
      `{iteration_id, seed{topic,source}, nara_summary, tool_calls_made,
        wrapper_call_ids[], journal_entry_path, started_at, ended_at, ...}`
  - LOOP_V0 orchestrator event (`week1.run.jsonl`, event_type starting `loop_v0_`):
      `{timestamp, event_type, iteration_id, [tool], [parent_request_id], ...}`
  - Generic orchestrator stage event (legacy / unchanged):
      `{stage, task_id, task_type, status, detail, ...}`
  - vLLM call event (`logs/calls.jsonl` and friends):
      `{request_id, parent_request_id, model, caller_tag, prompt_messages,
        completion, usage, latency_ms, host_metadata, ...}`
  - Unknown shapes in logs/ are projected generically; unknown shapes in
    run_state/ are skipped (state-dir is allowlist + strict).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CONSUMER_LOGS = REPO.parent / "a_bgt_rsi" / "logs"
CONSUMER_STATE = REPO.parent / "a_bgt_rsi" / "run_state"
CONSUMER_MEMORY = REPO.parent / "a_bgt_rsi" / "memory"
NARRATIVES = REPO / "memory" / "brain" / "narratives.jsonl"
EDGES = REPO / "memory" / "brain" / "edges.jsonl"

# Allowlist of state-like files. Each filename is searched for in any of the
# candidate dirs below — the apparatus split its ledgers between run_state/
# (execution traces) and memory/ (durable iteration records) over time.
# Dedup by (basename, line) keeps re-ingest safe across the move.
STATE_DIRS_CANDIDATE = (CONSUMER_STATE, CONSUMER_MEMORY)
STATE_FILES = ("loop_memory.jsonl", "week1.run.jsonl")

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(s: str) -> str:
    s = s.lower().strip()
    s = _SLUG_RE.sub("-", s)
    return s.strip("-") or "unnamed"


def _trim(s: str | None, n: int = 240) -> str:
    if not s:
        return ""
    s = str(s).strip()
    return s if len(s) <= n else s[:n] + "…"


def _last_user_msg(messages: list[dict] | None) -> str:
    if not messages:
        return ""
    for m in reversed(messages):
        if m.get("role") == "user":
            return _trim(m.get("content", ""))
    return _trim(messages[-1].get("content", ""))


def project_loop_v0_iteration(src: dict) -> dict:
    iid = src.get("iteration_id", "")
    seed = src.get("seed") or {}
    calls = src.get("wrapper_call_ids") or []
    tools = src.get("tool_calls_made") or []
    return {
        "agent_id": "nara",
        "task_id": iid,
        "intent": _trim(seed.get("topic", ""), 240),
        "did": _trim(src.get("nara_summary", ""), 400),
        "observed": (
            f"tools={len(tools)} calls={len(calls)} "
            f"journal={src.get('journal_entry_path', '')}"
        ),
        "_slug": _slugify(iid),
    }


def project_loop_v0_event(src: dict, lineno: int) -> dict:
    iid = src.get("iteration_id", "")
    ev = src.get("event_type", "")
    tool = src.get("tool") or "none"
    prid = src.get("parent_request_id")
    if tool != "none":
        did = f"tool={tool} status={src.get('status', 'n/a')}"
    elif ev.endswith("_start"):
        did = f"topic={_trim(src.get('topic', ''), 100)}"
    elif ev.endswith("_complete"):
        did = (
            f"duration_ms={src.get('duration_ms', 0)} "
            f"tool_calls_made={src.get('tool_calls_made', [])}"
        )
    else:
        did = ""
    return {
        "agent_id": f"nara:{ev}",
        "task_id": f"{iid}::{ev}::{tool}::L{lineno}",
        "intent": f"{ev} for {iid}",
        "did": did,
        "observed": f"parent_request_id={prid or 'n/a'}",
        "_slug": _slugify(f"event-{iid}-{ev}-{tool}-l{lineno}"),
    }


def project_orchestrator(src: dict) -> dict:
    stage = src.get("stage", "unknown")
    task_type = src.get("task_type", "")
    status = src.get("status", "")
    return {
        "agent_id": f"orchestrator:{stage}",
        "task_id": src.get("task_id", ""),
        "intent": f"{stage} for task_type={task_type}",
        "did": _trim(src.get("detail", "")),
        "observed": f"status={status}",
    }


def project_vllm_call(src: dict) -> dict:
    caller = src.get("caller_tag", "vllm_call")
    usage = src.get("usage", {}) or {}
    return {
        "agent_id": caller,
        "task_id": src.get("request_id", ""),
        "intent": _last_user_msg(src.get("prompt_messages")),
        "did": _trim(src.get("completion", ""), 300),
        "observed": (
            f"latency={src.get('latency_ms', 0):.0f}ms "
            f"tokens_in={usage.get('input_tokens', '?')} "
            f"tokens_out={usage.get('output_tokens', '?')} "
            f"model={src.get('model', '?')}"
        ),
    }


def project_generic(src: dict) -> dict:
    keys = [k for k in src.keys() if not k.startswith("_")]
    return {
        "agent_id": "unknown_apparatus",
        "task_id": src.get("task_id") or src.get("request_id", ""),
        "intent": "emit apparatus log entry",
        "did": _trim(f"fields: {', '.join(keys[:8])}"),
        "observed": _trim(json.dumps({k: src.get(k) for k in keys[:6]})),
    }


def project(src: dict, lineno: int, strict: bool) -> dict | None:
    """Dispatch to the right projection. Returns None to skip (state-dir strict mode)."""
    if "iteration_id" in src and "seed" in src and "nara_summary" in src:
        return project_loop_v0_iteration(src)
    if isinstance(src.get("event_type"), str) and src["event_type"].startswith("loop_v0_"):
        return project_loop_v0_event(src, lineno)
    if "stage" in src and "detail" in src:
        return project_orchestrator(src)
    if "prompt_messages" in src and "completion" in src:
        return project_vllm_call(src)
    if strict:
        return None
    return project_generic(src)


def load_existing_keys(path: Path) -> set[tuple[str, int]]:
    keys: set[tuple[str, int]] = set()
    if not path.exists():
        return keys
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("type") != "apparatus_event":
                continue
            src = obj.get("_source", {})
            if "file" in src and "line" in src:
                keys.add((src["file"], int(src["line"])))
    return keys


def load_existing_edges(path: Path) -> set[tuple[str, str, str]]:
    seen: set[tuple[str, str, str]] = set()
    if not path.exists():
        return seen
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            s, t, d = obj.get("src"), obj.get("type"), obj.get("dst")
            if s and t and d:
                seen.add((s, t, d))
    return seen


def build_calls_index(calls_path: Path) -> dict[str, str]:
    """request_id -> default slug `apparatus-calls-l<lineno>` for every call on disk."""
    idx: dict[str, str] = {}
    if not calls_path.exists():
        return idx
    with calls_path.open() as f:
        for lineno, raw in enumerate(f, 1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                continue
            rid = obj.get("request_id")
            if rid:
                idx[rid] = _slugify(f"apparatus-{calls_path.stem}-l{lineno}")
    return idx


def ingest_one(
    log_path: Path,
    existing: set[tuple[str, int]],
    strict: bool,
) -> list[tuple[dict, dict]]:
    """Project one JSONL file. Returns list of (narrative_entry, source_dict) pairs."""
    new_pairs: list[tuple[dict, dict]] = []
    with log_path.open() as f:
        for lineno, raw in enumerate(f, 1):
            raw = raw.strip()
            if not raw:
                continue
            key = (log_path.name, lineno)
            if key in existing:
                continue
            try:
                src = json.loads(raw)
            except json.JSONDecodeError as e:
                print(f"warn: {log_path.name}:{lineno} malformed JSON: {e}", file=sys.stderr)
                continue
            proj = project(src, lineno, strict=strict)
            if proj is None:
                continue
            entry = {
                "timestamp": src.get("timestamp") or src.get("started_at", ""),
                "task_id": proj["task_id"] or f"{log_path.stem}_L{lineno}",
                "agent_id": proj["agent_id"],
                "type": "apparatus_event",
                "intent": proj["intent"],
                "did": proj["did"],
                "observed": proj["observed"],
                "would_do_differently": "n/a — projected, not authored",
                "corrections_honored": [],
                "references": [
                    r for r in [src.get("parent_request_id"), src.get("request_id")] if r
                ],
                "_source": {
                    "file": log_path.name,
                    "line": lineno,
                    "request_id": src.get("request_id"),
                    "parent_request_id": src.get("parent_request_id"),
                },
            }
            if "_slug" in proj:
                entry["_slug"] = proj["_slug"]
            new_pairs.append((entry, src))
    return new_pairs


def _edge(ts: str, src: str, t: str, dst: str, source_event: str) -> dict:
    return {
        "timestamp": ts,
        "src": src,
        "src_type": "apparatus_event",
        "type": t,
        "dst": dst,
        "dst_type": "apparatus_event",
        "source_event": source_event,
        "agent_id": "ingest_apparatus",
    }


def derive_edges(
    new_pairs: list[tuple[dict, dict]],
    calls_index: dict[str, str],
    existing_edges: set[tuple[str, str, str]],
) -> list[dict]:
    """
    Three edge types:
      1. iteration --produced--> each LOOP_V0 event sharing iteration_id
      2. iteration --produced--> each vLLM call in wrapper_call_ids[]
      3. vLLM call --produced--> each LOOP_V0 event whose parent_request_id == call.request_id

    Idempotent: dedupes by (src, type, dst) against `existing_edges` (which is also
    mutated to prevent duplicate emits within this run).
    """
    edges: list[dict] = []

    # Index newly-projected narratives by slug and by iteration_id
    iteration_pairs: list[tuple[dict, dict]] = []
    event_pairs: list[tuple[dict, dict]] = []
    for narrative, src in new_pairs:
        slug = narrative.get("_slug", "")
        if narrative.get("agent_id") == "nara":
            iteration_pairs.append((narrative, src))
        elif isinstance(narrative.get("agent_id"), str) and narrative["agent_id"].startswith("nara:"):
            event_pairs.append((narrative, src))

    events_by_iter: dict[str, list[tuple[dict, dict]]] = defaultdict(list)
    for narrative, src in event_pairs:
        events_by_iter[src.get("iteration_id", "")].append((narrative, src))

    def _add(ts: str, s: str, t: str, d: str, src_event: str) -> None:
        key = (s, t, d)
        if key in existing_edges:
            return
        if not s or not d:
            return
        existing_edges.add(key)
        edges.append(_edge(ts, s, t, d, src_event))

    # 1 & 2: iteration → produced → events + calls
    for narrative, src in iteration_pairs:
        iter_slug = narrative.get("_slug", "")
        iid = src.get("iteration_id", "")
        ts = src.get("started_at", "") or src.get("timestamp", "")
        for ev_narr, _ev_src in events_by_iter.get(iid, []):
            _add(ts, iter_slug, "produced", ev_narr.get("_slug", ""), iid)
        for rid in src.get("wrapper_call_ids") or []:
            dst = calls_index.get(rid)
            if dst:
                _add(ts, iter_slug, "produced", dst, iid)

    # 3: vLLM call → produced → events triggered by that call
    for ev_narr, ev_src in event_pairs:
        prid = ev_src.get("parent_request_id")
        if not prid:
            continue
        call_slug = calls_index.get(prid)
        if not call_slug:
            continue
        iid = ev_src.get("iteration_id", "")
        ts = ev_src.get("timestamp", "")
        _add(ts, call_slug, "produced", ev_narr.get("_slug", ""), iid)

    return edges


def main() -> int:
    parser = argparse.ArgumentParser(description="Project apparatus logs into narratives + edges.")
    parser.add_argument(
        "--logs-dir",
        default=str(CONSUMER_LOGS),
        help=f"Apparatus logs directory (default: {CONSUMER_LOGS})",
    )
    parser.add_argument(
        "--state-dir",
        action="append",
        default=None,
        help=f"Apparatus state-like directory (repeatable). "
             f"Default candidates: {[str(p) for p in STATE_DIRS_CANDIDATE]}; "
             f"strict allowlist within each: {STATE_FILES}",
    )
    parser.add_argument(
        "--narratives",
        default=str(NARRATIVES),
        help=f"Narratives ledger (default: {NARRATIVES})",
    )
    parser.add_argument(
        "--edges",
        default=str(EDGES),
        help=f"Edges ledger (default: {EDGES})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute new entries but do not write.",
    )
    args = parser.parse_args()

    logs_dir = Path(args.logs_dir)
    state_dirs = (
        [Path(p) for p in args.state_dir] if args.state_dir
        else list(STATE_DIRS_CANDIDATE)
    )
    narratives = Path(args.narratives)
    edges_path = Path(args.edges)
    if not logs_dir.is_dir():
        print(f"error: logs directory not found: {logs_dir}", file=sys.stderr)
        return 2
    narratives.parent.mkdir(parents=True, exist_ok=True)
    narratives.touch(exist_ok=True)
    edges_path.parent.mkdir(parents=True, exist_ok=True)
    edges_path.touch(exist_ok=True)

    # Collect log files: main logs dir + sibling worktree logs dirs.
    consumer_root = logs_dir.parent
    worktree_log_dirs = sorted(consumer_root.glob(".claude/worktrees/*/logs"))
    log_paths: list[tuple[Path, bool]] = []  # (path, strict)
    for d in [logs_dir, *worktree_log_dirs]:
        for p in sorted(d.glob("*.jsonl")):
            log_paths.append((p, False))

    # State files: allowlist + strict (unknown shapes are skipped, not generic-projected).
    # Scan every candidate dir for each allowlisted filename. Duplicates across
    # dirs are safe — (basename, line) dedup makes re-ingest idempotent.
    for d in state_dirs:
        if not d.is_dir():
            continue
        for name in STATE_FILES:
            p = d / name
            if p.exists():
                log_paths.append((p, True))

    # Build calls_index from ALL calls.jsonl entries on disk (needed for edges)
    calls_index = build_calls_index(logs_dir / "calls.jsonl")

    existing_narrative_keys = load_existing_keys(narratives)
    existing_edge_keys = load_existing_edges(edges_path)

    all_new_pairs: list[tuple[dict, dict]] = []
    per_file: dict[str, int] = {}
    for log_path, strict in log_paths:
        before = len(all_new_pairs)
        all_new_pairs.extend(ingest_one(log_path, existing_narrative_keys, strict=strict))
        report_key = log_path.name
        if ".claude/worktrees/" in str(log_path):
            wt = log_path.parts[log_path.parts.index("worktrees") + 1]
            report_key = f"{log_path.name} (wt:{wt})"
        elif strict:
            report_key = f"{log_path.name} ({log_path.parent.name})"
        per_file[report_key] = len(all_new_pairs) - before

    new_edges = derive_edges(all_new_pairs, calls_index, existing_edge_keys)

    if not all_new_pairs and not new_edges:
        print(
            f"no new apparatus events or edges to ingest "
            f"(existing apparatus_event keys: {len(existing_narrative_keys)}, "
            f"edges: {len(existing_edge_keys)})"
        )
        return 0

    if args.dry_run:
        print(f"DRY RUN — would append {len(all_new_pairs)} narratives, {len(new_edges)} edges")
        for name, n in per_file.items():
            if n:
                print(f"  narratives {name}: +{n}")
        if new_edges:
            edge_summary: dict[str, int] = defaultdict(int)
            for e in new_edges:
                edge_summary[e["type"]] += 1
            for t, n in sorted(edge_summary.items()):
                print(f"  edges {t}: +{n}")
        return 0

    with narratives.open("a") as f:
        for entry, _src in all_new_pairs:
            f.write(json.dumps(entry, separators=(",", ":")) + "\n")
    with edges_path.open("a") as f:
        for e in new_edges:
            f.write(json.dumps(e, separators=(",", ":")) + "\n")

    print(
        f"appended {len(all_new_pairs)} apparatus events to {narratives}, "
        f"{len(new_edges)} edges to {edges_path}"
    )
    for name, n in per_file.items():
        if n:
            print(f"  narratives {name}: +{n}")
    if new_edges:
        edge_summary: dict[str, int] = defaultdict(int)
        for e in new_edges:
            edge_summary[e["type"]] += 1
        for t, n in sorted(edge_summary.items()):
            print(f"  edges {t}: +{n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
