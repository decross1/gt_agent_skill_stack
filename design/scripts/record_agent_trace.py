#!/usr/bin/env python3
"""record_agent_trace.py — Agent Trace 5-tuple & MindSkillEvolve Distillation Helper.

Records code/UI mutations in the Agent Trace 5-tuple format (`what`, `when`,
`who`, `why`, `where`) and optionally formats a ReHarness backward qualification
row (`reharness-qualification/v1`) or `harvest` feedback entry (`memory/feedback.jsonl`).
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

TRACE_SCHEMA = "agent-trace/v1"
ZERO_SHA = "0" * 64


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def build_trace_entry(
    *,
    what: str,
    who: str,
    why: str,
    where: str,
    when: str | None = None,
    skills_active: list[str] | None = None,
    qa_metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ts = when or utcnow_iso()
    payload = {
        "schema": TRACE_SCHEMA,
        "what": what.strip(),
        "when": ts,
        "who": who.strip(),
        "why": why.strip(),
        "where": where.strip(),
        "skills_active": skills_active or [],
        "qa_metrics": qa_metrics or {},
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    payload["trace_sha256"] = hashlib.sha256(raw).hexdigest()
    return payload


def build_qualification_row(
    *,
    qualification_id: str,
    prev_sha256: str,
    skill_path: str,
    skill_commit: str,
    skill_blob_sha: str,
    trigger_run_ref: str,
    applies_when: list[dict[str, Any]],
    falsified_when: list[dict[str, Any]],
    scope_narrowing: str,
) -> dict[str, Any]:
    core = {
        "schema": "reharness-qualification/v1",
        "qualification_id": qualification_id,
        "prev_sha256": prev_sha256,
        "skill_path": skill_path,
        "skill_commit": skill_commit,
        "skill_blob_sha": skill_blob_sha,
        "trigger_run_ref": trigger_run_ref,
        "applies_when": applies_when,
        "falsified_when": falsified_when,
        "scope_narrowing": scope_narrowing,
    }
    raw = json.dumps(core, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    core["row_sha256"] = hashlib.sha256(raw).hexdigest()
    return core


def build_feedback_entry(
    *,
    harvest_id: str,
    source: str,
    ref: str,
    skill: str,
    finding_class: str,
    evidence: str,
    plan_candidate: str | None = None,
    date: str | None = None,
) -> dict[str, Any]:
    if finding_class not in {"confirmed", "diverged", "gap", "friction"}:
        raise ValueError(f"invalid finding_class: {finding_class!r}")
    return {
        "harvest_id": harvest_id.strip(),
        "date": (date or utcnow_iso())[:10],
        "source": source.strip(),
        "ref": ref.strip(),
        "skill": skill.strip(),
        "class": finding_class,
        "evidence": evidence.strip(),
        "plan_candidate": plan_candidate,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--what", required=True, help="Entity path / AST or UI state diff")
    parser.add_argument("--who", required=True, help="Agent runtime / model / session ID")
    parser.add_argument("--why", required=True, help="Reasoning trace and active skill constraints")
    parser.add_argument("--where", required=True, help="Git commit or branch")
    parser.add_argument("--skills", default="", help="Comma-separated active skills")
    parser.add_argument("--out", type=Path, default=None, help="Optional JSONL file to append")
    args = parser.parse_args(argv)

    skills = [s.strip() for s in args.skills.split(",") if s.strip()]
    entry = build_trace_entry(
        what=args.what,
        who=args.who,
        why=args.why,
        where=args.where,
        skills_active=skills,
    )
    line = json.dumps(entry, sort_keys=True)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
