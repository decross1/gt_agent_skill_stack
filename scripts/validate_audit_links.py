#!/usr/bin/env python3
"""Read-only identity checks before appending framework audit links.

Resolve a decision by its exact heading/date and title, or check a JSONL file
of pending edges against framework decisions and non-runtime narratives.
Uses existing projector identities; no projected pages, consumer files, services
or ledger writers are invoked. Unknown or ambiguous endpoints fail closed.

Receipts bind the bytes examined. They do not lock a later append, authenticate
an actor, retract historical edges, or establish that a decision was enacted.
Recheck changed inputs before appending through the existing governed process.
source_event is a declared task/narrative label; its existence is not checked.
Timestamp syntax does not authenticate an event or establish when it occurred.
"""
from __future__ import annotations

import sys

# Keep normal CLI use read-only, including imports of local projector helpers.
if __name__ == "__main__":
    sys.dont_write_bytecode = True

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

from project_pages import narrative_slug, parse_decisions

REPO = Path(__file__).resolve().parents[1]
DECISIONS = "memory/DECISIONS.md"
NARRATIVES = "memory/brain/narratives.jsonl"
RELATIONS = {"derived_from", "produced", "linked_to", "falsified_by",
             "supersedes", "references"}
SCOPE = "framework decisions and non-apparatus narratives only"

# Recorded calendar date-times: T/space, seconds, optional fraction and offset.
# Guard component ranges before fromisoformat, which normalizes e.g. +01:99.
_RECORDED_DATETIME = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}[T ](?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]"
    r"(?:\.[0-9]+)?(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])?"
)


def parse_recorded_datetime(value: object) -> datetime | None:
    """Parse the recorded calendar convention, without inferring event truth.

    Naive values remain naive; valid future dates are allowed. The returned
    date-time retains its recorded offset and calendar day, not a UTC substitute.
    Unsupported/missing/malformed values return None; source bytes stay intact.
    """
    if not isinstance(value, str) or not _RECORDED_DATETIME.fullmatch(value):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _snapshot(path: Path) -> tuple[str, str]:
    data = path.read_bytes()
    return data.decode("utf-8"), hashlib.sha256(data).hexdigest()


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON member: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"nonstandard JSON constant: {value}")


def _rows(text: str, source: str) -> list[tuple[int, dict]]:
    rows = []
    for line, raw in enumerate(text.splitlines(), 1):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw, object_pairs_hook=_unique_object,
                             parse_constant=_reject_constant)
        except ValueError as exc:
            raise ValueError(f"{source}:{line}: malformed JSON: {exc}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{source}:{line}: expected a JSON object")
        rows.append((line, row))
    return rows


def resolve_decision(repo_root: Path, head: str, title: str) -> dict:
    """Resolve an exact source heading; never guess from a hand-made slug."""
    repo_root = repo_root.resolve()
    source_path = (repo_root / DECISIONS).resolve()
    text, digest = _snapshot(source_path)
    decisions = parse_decisions(text, "framework")
    matches = [d for d in decisions if d["head"] == head and d["title"] == title]
    if len(matches) != 1:
        raise ValueError(f"decision heading/title unresolved or ambiguous: {len(matches)} matches")
    decision = matches[0]
    if sum(d["slug"] == decision["slug"] for d in decisions) != 1:
        raise ValueError("ambiguous projected decision ID; distinct headings collide")
    return {"ok": True, "slug": decision["slug"], "type": decision["type"],
            "source": DECISIONS, "head": head, "title": title,
            "repo_root": str(repo_root), "source_path": str(source_path),
            "source_sha256": digest, "authority_verified": False,
            "append_performed": False}


def validate_candidates(repo_root: Path, edges_path: Path) -> dict:
    """Check every supplied edge, retaining physical line numbers and failures.

    `supersedes` remains a node relation, never a command to erase another edge.
    A corrected append cannot make an earlier dangling edge pass this check.
    """
    repo_root = repo_root.resolve()
    edges_path = edges_path.resolve()
    source_paths = {name: (repo_root / name).resolve()
                    for name in (DECISIONS, NARRATIVES)}
    decision_text, decision_digest = _snapshot(source_paths[DECISIONS])
    narrative_text, narrative_digest = _snapshot(source_paths[NARRATIVES])
    edge_text, edge_digest = _snapshot(edges_path)
    nodes: dict[str, list[str]] = {}
    for decision in parse_decisions(decision_text, "framework"):
        nodes.setdefault(decision["slug"], []).append(decision["type"])
    for line, row in _rows(narrative_text, NARRATIVES):
        if row.get("type") == "apparatus_event":
            continue  # Outside this declared framework-only check.
        identity = row.get("_slug") or row.get("task_id")
        kind = row.get("_type_override") or "reflection"
        if (not isinstance(identity, str) or not identity.strip()
                or not isinstance(kind, str) or not kind.strip()):
            raise ValueError(f"{NARRATIVES}:{line}: missing or malformed narrative identity/type")
        nodes.setdefault(narrative_slug(row), []).append(kind)

    rows = _rows(edge_text, str(edges_path))
    if not rows:
        raise ValueError("no candidate edges supplied; nothing was validated")
    errors = []

    def error(line: int, field: str, reason: str) -> None:
        errors.append({"line": line, "field": field, "reason": reason})

    for line, row in rows:
        invalid = set()
        for field in ("src", "dst", "src_type", "dst_type", "type",
                      "timestamp", "source_event", "agent_id"):
            if not isinstance(row.get(field), str) or not row[field].strip():
                error(line, field, "expected a nonempty recorded string")
                invalid.add(field)
        if "type" not in invalid and row["type"] not in RELATIONS:
            error(line, "type", "unsupported declared audit relation")
        if "timestamp" not in invalid and parse_recorded_datetime(row["timestamp"]) is None:
            error(line, "timestamp", "expected a valid recorded ISO calendar date-time")
        for endpoint in ("src", "dst"):
            if endpoint in invalid or endpoint + "_type" in invalid:
                continue
            matches = nodes.get(row[endpoint], [])
            if not matches:
                error(line, endpoint, "unresolved endpoint in declared framework scope")
            elif len(matches) != 1:
                error(line, endpoint, "ambiguous endpoint identity in source records")
            elif matches[0] != row[endpoint + "_type"]:
                error(line, endpoint + "_type", "declared type differs from source entity type")

    return {"ok": not errors, "scope": SCOPE, "checked": len(rows),
            "repo_root": str(repo_root),
            "source_paths": {name: str(path) for name, path in source_paths.items()},
            "candidate_path": str(edges_path),
            "errors": errors, "source_sha256": {DECISIONS: decision_digest,
                                                   NARRATIVES: narrative_digest},
            "candidate_sha256": edge_digest, "authority_verified": False,
            "append_performed": False,
            "limitation": "snapshot check only; changed inputs require revalidation; "
                          "source_event existence and actor labels are not authenticated; "
                          "valid timestamp syntax is not event verification"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO)
    commands = parser.add_subparsers(dest="command", required=True)
    resolve = commands.add_parser("resolve-decision", help="resolve an exact framework heading/title")
    resolve.add_argument("--head", required=True)
    resolve.add_argument("--title", required=True)
    check = commands.add_parser("check", help="check pending JSONL edges; never append")
    check.add_argument("--edges", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = (resolve_decision(args.repo_root, args.head, args.title)
                  if args.command == "resolve-decision"
                  else validate_candidates(args.repo_root, args.edges))
    except (OSError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc), "scope": SCOPE,
                          "authority_verified": False, "append_performed": False}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
