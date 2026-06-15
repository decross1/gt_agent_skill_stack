#!/usr/bin/env python3
"""verify_brain_view.py — gate the brain's view artifacts before they are trusted.

Five check families, each an independent pass/fail (a near-miss is a fail):
  1. determinism — two in-process build_summary() calls against one clock are
     deep-equal once generated_at is nulled.
  2. schema — summary.json carries every v2 top-level key; enums hold for
     inbox kind/severity, governance.state, contracts.done_check, loop.state,
     agent kind/evidence; matrix cells resolve to known agents/skills; by_day
     buckets stay inside the trailing window; timeline rows are windowed with
     <=100-char titles.
  3. cross-derivation — counts re-derived from the raw ledgers (not through
     project_summary's builders) match the emitted numbers.
  4. map_data.js (when present) — parses, no excluded mechanical node types,
     all edge endpoints resolve, <=400 nodes, <300KB.
  5. file parity — summary_data.js parses and deep-equals summary.json.

Run with BRAIN_CONSUMER_ROOT set (same resolution as the generator). Exit 0
only when every check passes.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
from datetime import date as date_cls, datetime, timedelta, timezone
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import project_summary as ps  # noqa: E402

TOP_KEYS = {"schema_version", "generated_at", "repo", "consumer", "window",
            "status_strip", "inbox", "agents", "skills", "matrix", "contracts",
            "loop", "timeline", "incidents", "rules", "attribution", "days"}
INBOX_KINDS = {"gate_verdict", "proposal_review", "bubble_unacked",
               "finding_review", "stale_run", "drift", "contract_unverified"}
SEVERITIES = {"high", "med", "low"}
GOV_STATES = {"ok", "drift", "healed", "new", "untested", "by_design",
              "firewall_violation"}
DONE_CHECKS = {"pass", "fail", "inconclusive", "freeform", "unverified", "pending"}
LOOP_STATES = {"active", "half-dormant", "dormant"}
AGENT_KINDS = {"dev", "runtime", "human"}
EVIDENCE = {"explicit", "mixed", "inferred"}
D042_BY_DESIGN = {"orchestrate", "experiment", "repro-check", "plan-research"}
# The dashboard map is the agent <-> skill layer; mechanical graph kinds must
# not leak into it.
MAP_EXCLUDED_TYPES = {"apparatus_event", "orchestrator_event", "llm_call",
                      "iteration", "stage", "run_log_entry"}
MAP_MAX_NODES, MAP_MAX_BYTES = 400, 300_000

# --- dynamic proposal-review feature (D-046 human-write-back) ---------------
# Every "card" entry the brain UI persists to proposal_cards.jsonl must carry
# these keys (the GET /api/proposal/<P-NNN> contract's `card` object).
CARD_KEYS = {"means", "pros_accept", "cons_accept", "pros_reject", "cons_reject",
             "rule_check"}
PROPOSAL_CARDS = ps.REPO / "memory" / "brain" / "proposal_cards.jsonl"
# The blessed verdict CLI's frozen accept-arg enum (review_proposal_cli.VERDICTS
# keys). Projection NEVER enacts a verdict; the UI execs this CLI via argv.
VERDICT_ENUM = {"accept", "reject", "needs_revision"}
REVIEW_CLI = _SCRIPTS / "review_proposal_cli.py"
# Determinism guard — the projection path (project_summary + the loaders it
# imports from project_pages) must not be able to reach the LLM, so a regen is
# pure file→file. These source files are grepped for any LLM reach.
PROJECTION_SOURCES = [_SCRIPTS / "project_summary.py", _SCRIPTS / "project_pages.py"]
# Anything that would let projection call Gemma: the HTTP client modules, the
# OpenAI-compatible endpoint path, or the Gemma host:port.
LLM_REACH_RE = re.compile(
    r"\bimport\s+urllib\b|\bfrom\s+urllib\b|\burllib\.|\bimport\s+requests\b"
    r"|\brequests\.|/v1/chat/completions|127\.0\.0\.1:8000|localhost:8000"
    r"|\bgemma\b",
    re.IGNORECASE)

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(ok), detail))


def jsonl(path: Path) -> list[dict]:
    out = []
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return out


def parse_js_object(text: str) -> dict | None:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None


def in_window(d: str, win_start: str, win_end: str) -> bool:
    return bool(d) and win_start <= d <= win_end


def check_schema(s: dict) -> None:
    check("schema: top-level keys", set(s.keys()) == TOP_KEYS,
          f"missing={sorted(TOP_KEYS - set(s))} extra={sorted(set(s) - TOP_KEYS)}")
    check("schema: schema_version == 2", s.get("schema_version") == 2)
    w = s.get("window") or {}
    win_end = w.get("newest_event") or ""
    try:
        win_start = (date_cls.fromisoformat(win_end)
                     - timedelta(days=int(w.get("max_days", 7)) - 1)).isoformat()
    except (ValueError, TypeError):
        win_start = ""
    check("schema: window fields", all(k in w for k in
          ("default_days", "min_days", "max_days", "oldest_event", "newest_event"))
          and bool(win_start), str(sorted(w)))
    strip = s.get("status_strip") or {}
    check("schema: status_strip", strip.get("system") in ("ok", "attention", "critical")
          and strip.get("loop", {}).get("state") in LOOP_STATES
          and all(k in strip for k in
                  ("needs_you", "drift", "loop", "firewall", "freshness")))
    bad = [i["id"] for i in s["inbox"]
           if i.get("kind") not in INBOX_KINDS or i.get("severity") not in SEVERITIES
           or not isinstance(i.get("link"), dict)]
    check("schema: inbox kind/severity/link enums", not bad, f"bad={bad[:4]}")
    bad = [a["id"] for a in s["agents"]
           if a.get("kind") not in AGENT_KINDS or a.get("evidence") not in EVIDENCE
           or any(not in_window(d, win_start, win_end) for d in a.get("runs_by_day", {}))]
    check("schema: agents kind/evidence + runs_by_day windowed", not bad, f"bad={bad[:4]}")
    bad = [k["name"] for k in s["skills"]
           if (k.get("governance") or {}).get("state") not in GOV_STATES]
    check("schema: governance.state enum", not bad, f"bad={bad[:4]}")
    bad = [c["spawn_id"] for c in s["contracts"] if c.get("done_check") not in DONE_CHECKS]
    check("schema: contracts.done_check enum", not bad, f"bad={bad[:4]}")
    agent_ids = {a["id"] for a in s["agents"]}
    skill_names = {k["name"] for k in s["skills"]}
    bad = [f"{c['agent']}×{c['skill']}" for c in s["matrix"]["cells"]
           if c["agent"] not in agent_ids or c["skill"] not in skill_names
           or any(not in_window(d, win_start, win_end) for d in c.get("by_day", {}))]
    check("schema: matrix cells resolve + by_day windowed", not bad, f"bad={bad[:4]}")
    check("schema: loop.state enum", (s.get("loop") or {}).get("state") in LOOP_STATES)
    bad = [t["id"] for t in s["timeline"]
           if not in_window(t.get("date", ""), win_start, win_end)
           or len(t.get("title") or "") > 100]
    check("schema: timeline windowed, titles <=100", not bad, f"bad={bad[:4]}")


def check_cross(s: dict, consumer: Path | None) -> None:
    fb_ids = {r.get("iteration_id")
              for r in jsonl(consumer / "memory" / "loop_feedback.jsonl")} if consumer else set()
    pend = [r for r in (jsonl(consumer / "memory" / "loop_memory.jsonl") if consumer else [])
            if r.get("gate_status") == "pending"
            and r.get("iteration_id") and r["iteration_id"] not in fb_ids]
    got = sum(1 for i in s["inbox"] if i["kind"] == "gate_verdict")
    check("cross: pending gates == loop_memory pending − loop_feedback ids",
          got == len(pend), f"inbox={got} rederived={len(pend)}")

    # Mirror the generator: only framework-scoped open/human-review proposals
    # become inbox items; research-scoped ones (consumer apparatus) are filtered.
    cname = consumer.name if consumer is not None else None
    collapsed = ps.collapse_proposals(jsonl(ps.PROPOSALS))
    want = sum(1 for p in collapsed.values()
               if ps.final_verdict(p) in ("open", "human-review")
               and ps.proposal_scope(p["first"], cname) == "framework")
    got = sum(1 for i in s["inbox"] if i["kind"] == "proposal_review")
    check("cross: proposal_review == framework open+human-review latest verdicts",
          got == want, f"inbox={got} rederived={want}")

    skill_mds = sorted((ps.REPO / ".agents" / "skills").glob("*/SKILL.md"))
    check("cross: len(skills) == 24", len(s["skills"]) == 24 == len(skill_mds),
          f"summary={len(s['skills'])} dirs={len(skill_mds)}")
    rt_disk = sum(1 for p in skill_mds
                  if re.search(r"^runtime-safe:\s*true\b", p.read_text()[:600], re.M))
    rt_sum = sum(1 for k in s["skills"] if k["runtime_safe"])
    check("cross: runtime_safe count == 6", rt_sum == 6 == rt_disk,
          f"summary={rt_sum} disk={rt_disk}")
    by_design = {k["name"] for k in s["skills"]
                 if k["governance"]["referenced_only_by_design"]}
    check("cross: by_design set == D-042 four", by_design == D042_BY_DESIGN,
          f"got={sorted(by_design)}")
    check("cross: needs_you.total == len(inbox)",
          s["status_strip"]["needs_you"]["total"] == len(s["inbox"]),
          f"strip={s['status_strip']['needs_you']['total']} inbox={len(s['inbox'])}")

    used = 0
    for path in ([consumer / "run_state" / "week1.run.jsonl"] if consumer else []) + \
                [ps.REPO / "run_state" / "framework.run.jsonl"]:
        used += sum(1 for r in jsonl(path) if (r.get("skill_used") or "").strip())
    explicit = sum(c["explicit"] for c in s["matrix"]["cells"])
    check("cross: explicit matrix total == skill_used rows in both run logs",
          explicit == used == s["attribution"]["skill_used_rows"],
          f"matrix={explicit} rederived={used} attribution={s['attribution']['skill_used_rows']}")


def check_map(view_dir: Path) -> None:
    p = view_dir / "map_data.js"
    if not p.exists():
        check("map: map_data.js", True, "absent — skipped")
        return
    payload = parse_js_object(p.read_text())
    check("map: parses", payload is not None)
    if payload is None:
        return
    nodes = payload.get("nodes") or []
    edges = payload.get("edges") or []
    bad_types = sorted({n.get("type") for n in nodes} & MAP_EXCLUDED_TYPES)
    check("map: no excluded node types", not bad_types, f"found={bad_types}")
    ids = {n.get("id") for n in nodes}
    dangling = [e for e in edges if not (
        (e.get("src") or e.get("source") or e.get("from")) in ids
        and (e.get("dst") or e.get("target") or e.get("to")) in ids)]
    check("map: all edge endpoints resolve", not dangling, f"dangling={len(dangling)}")
    check("map: <=400 nodes", len(nodes) <= MAP_MAX_NODES, f"nodes={len(nodes)}")
    check("map: <300KB", p.stat().st_size < MAP_MAX_BYTES, f"bytes={p.stat().st_size}")


def check_proposal_cards() -> None:
    """proposal_cards.jsonl (when present): every line parses as a JSON object,
    and every `kind == 'card'` entry carries the six card keys. Discussion rows
    and other entry kinds are not card-shaped and are intentionally ignored.
    Absent file → skip (the feature may not have run yet)."""
    if not PROPOSAL_CARDS.exists():
        check("proposal_cards: proposal_cards.jsonl", True, "absent — skipped")
        return
    lines = [l for l in PROPOSAL_CARDS.read_text().splitlines() if l.strip()]
    bad_parse: list[int] = []
    rows: list[dict] = []
    for n, line in enumerate(lines, 1):
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            bad_parse.append(n)
            continue
        if isinstance(obj, dict):
            rows.append(obj)
        else:
            bad_parse.append(n)
    check("proposal_cards: every line parses as a JSON object", not bad_parse,
          f"bad_lines={bad_parse[:6]}")
    cards = [r for r in rows if r.get("kind") == "card"]
    missing = [(r.get("proposal_id") or "?", sorted(CARD_KEYS - set(r)))
               for r in cards if not CARD_KEYS <= set(r)]
    check("proposal_cards: each card has means/pros_accept/cons_accept/"
          "pros_reject/cons_reject/rule_check", not missing,
          f"cards={len(cards)} missing={missing[:4]}")


def check_determinism_guard() -> None:
    """Projection must be pure file→file: project_summary.py and the projection
    path it imports (project_pages.py) must not import urllib/requests or name
    the Gemma endpoint, so a regen can never reach the LLM."""
    for src in PROJECTION_SOURCES:
        name = src.name
        if not src.exists():
            check(f"determinism: {name} present for LLM-reach grep", False,
                  "source file missing")
            continue
        hits = sorted({m.group(0).strip()
                       for m in LLM_REACH_RE.finditer(src.read_text())})
        check(f"determinism: {name} has no urllib/requests/Gemma reach",
              not hits, f"hits={hits[:6]}")


def check_verdict_enum() -> None:
    """review_proposal_cli.py exposes the frozen verdict enum exactly
    {accept, reject, needs_revision}. Absent CLI → skip."""
    if not REVIEW_CLI.exists():
        check("verdict-enum: review_proposal_cli.py", True, "absent — skipped")
        return
    spec = importlib.util.spec_from_file_location("_review_proposal_cli", REVIEW_CLI)
    try:
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # __main__-guarded: import has no side effects
        keys = set(getattr(mod, "VERDICTS", {}).keys())
    except Exception as e:  # noqa: BLE001 — record, don't mask
        check("verdict-enum: review_proposal_cli.py importable", False, repr(e))
        return
    check("verdict-enum: VERDICTS keys == {accept,reject,needs_revision}",
          keys == VERDICT_ENUM,
          f"got={sorted(keys)} want={sorted(VERDICT_ENUM)}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Verify brain view artifacts (exit !=0 on failure).")
    ap.add_argument("--view-dir", type=Path, default=ps.VIEW_DIR,
                    help="Directory holding summary.json/summary_data.js (default: memory/brain/view).")
    args = ap.parse_args()

    now = datetime.now(timezone.utc)
    b1, b2 = ps.build_summary(now), ps.build_summary(now)
    check("determinism: double build deep-equal (generated_at nulled)",
          dict(b1, generated_at=None) == dict(b2, generated_at=None))

    json_path = args.view_dir / "summary.json"
    js_path = args.view_dir / "summary_data.js"
    if not json_path.exists():
        # Generated projection (P-013): absent on a fresh checkout until rebuilt.
        check("artifact: summary.json present", True,
              "absent — generated; run scripts/regen_brain.sh to build")
        s = None
    else:
        try:
            s = json.loads(json_path.read_text())
            check("artifact: summary.json readable", True)
        except (OSError, json.JSONDecodeError) as e:
            check("artifact: summary.json readable", False, str(e))
            s = None
    if s is not None:
        try:
            check_schema(s)
            env = os.environ.get("BRAIN_CONSUMER_ROOT") or s.get("consumer")
            consumer = Path(env) if env and Path(env).exists() else None
            check_cross(s, consumer)
        except Exception as e:  # noqa: BLE001 — record, don't mask, then exit 1
            check("verifier: schema/cross checks ran to completion", False, repr(e))
        js_text = js_path.read_text() if js_path.exists() else ""
        js_obj = parse_js_object(js_text)
        check("parity: summary_data.js is exactly `window.BRAIN_SUMMARY = {...};`",
              js_text.startswith("window.BRAIN_SUMMARY = ")
              and js_text.rstrip().endswith(";") and js_obj is not None)
        check("parity: summary_data.js deep-equals summary.json", js_obj == s)
    check_map(args.view_dir)

    # Dynamic proposal-review feature (tolerant when its files are absent).
    check_proposal_cards()
    check_determinism_guard()
    check_verdict_enum()

    failed = [r for r in RESULTS if not r[1]]
    for name, ok, detail in RESULTS:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}"
              + (f"  ({detail})" if detail else ""))
    print(f"verify_brain_view: {len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed"
          f" — view dir {args.view_dir}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
