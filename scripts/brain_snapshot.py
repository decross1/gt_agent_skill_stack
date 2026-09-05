#!/usr/bin/env python3
"""
N4 — brain-compounding snapshot.

Reads the brain to report three recorded quantities. These are descriptive
proxies, not evidence of improvement. Designed to be invoked once per
session at resume time by [[resume-state]].

Metrics:
  (a) active rules — count of FR-NNN/AR-NNN in memory/brain/rules.md
  (b) days since last recorded terminal proposal closure (any actor)
  (c) median recorded time-to-resume — seconds between explicit session_start
      and first task_start receipts sharing a session_id (latest K sessions).
      Historical task names alone cannot establish either boundary.

Usage: python scripts/brain_snapshot.py [--sessions 5]
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

from brain_ledger import inspect_proposals, ProposalLedgerError

REPO = Path(__file__).resolve().parent.parent
RULES_MD = REPO / "memory" / "brain" / "rules.md"
PROPOSALS = REPO / "memory" / "brain" / "proposals.jsonl"
FW_RUN = REPO / "run_state" / "framework.run.jsonl"

RULE_ID_RE = re.compile(r"^###\s+(FR-\d+|AR-\d+)\s+—", re.MULTILINE)


def parse_ts(s: str) -> datetime | None:
    if not isinstance(s, str) or not s:
        return None
    try:
        ts = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return ts if ts.tzinfo is not None else None


def read_rows(path: Path):
    """Missing ledgers have no observations; malformed ledgers are errors."""
    if not path.exists():
        return
    with path.open() as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSON") from exc
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_no}: expected a JSON object")
            yield line_no, row


def observation_time(path: Path, line_no: int, row: dict, now: datetime) -> datetime:
    ts = parse_ts(row.get("timestamp"))
    if ts is None or ts > now:
        raise ValueError(f"{path}:{line_no}: timestamp must be timezone-aware and not in the future")
    return ts


def count_active_rules() -> int:
    if not RULES_MD.exists():
        return 0
    text = RULES_MD.read_text()
    return len(RULE_ID_RE.findall(text))


def days_since_last_human_review() -> float | None:
    """Compatibility name; closures include every actor, without authentication."""
    return days_since_last_proposal_closed()


def days_since_last_proposal_closed() -> float | None:
    """Use governed rows and retain physical positions around legacy quarantine."""
    now = datetime.now(timezone.utc)
    try:
        observed = inspect_proposals(PROPOSALS, quarantine_known_legacy=True)
    except ProposalLedgerError as exc:
        # Preserve the validator's failure; attach the source path, never fall
        # back to permissive JSONL intake.
        message = re.sub(r"^line (\d+):", r"\1:", str(exc))
        raise ValueError(f"{PROPOSALS}:{message}") from exc
    excluded = {item["line_number"] for item in observed.quarantine}
    positions = (line for line in range(1, len(observed.rows) + len(excluded) + 1)
                 if line not in excluded)
    closures = [
        observation_time(PROPOSALS, line_no, row, now)
        for line_no, row in zip(positions, observed.rows)
        if row.get("status") == "closed"
        and row.get("verdict") in {"accepted", "rejected", "auto-accept", "auto-reject"}
    ]
    return (now - max(closures)).total_seconds() / 86400.0 if closures else None


def median_time_to_resume(k: int) -> float | None:
    """Use explicit optional receipts only; never infer boundaries from task IDs.

    Receipts use kind=session_start|task_start, a shared nonempty session_id,
    and an aware timestamp. A task receipt must follow its one session start in
    append order. Reused session IDs and negative first intervals are ambiguous.
    Recognizing these observations does not require or emit a new log schema.
    """
    if k < 1:
        raise ValueError("session window must be positive")
    now = datetime.now(timezone.utc)
    sessions: dict[str, list[tuple[str, datetime]]] = {}
    for line_no, row in read_rows(FW_RUN):
        kind, sid = row.get("kind"), row.get("session_id")
        if kind not in {"session_start", "task_start"}:
            continue
        if not isinstance(sid, str) or not sid.strip():
            raise ValueError(f"{FW_RUN}:{line_no}: receipt needs a nonempty session_id")
        ts = observation_time(FW_RUN, line_no, row, now)
        sessions.setdefault(sid, []).append((kind, ts))

    measured: list[tuple[datetime, float]] = []
    for entries in sessions.values():
        starts = [i for i, (kind, _) in enumerate(entries) if kind == "session_start"]
        if len(starts) != 1 or starts[0] != 0:
            continue
        index = starts[0]
        start = entries[index][1]
        first_task = next((ts for kind, ts in entries[index + 1:] if kind == "task_start"), None)
        if first_task is not None and first_task >= start:
            measured.append((start, (first_task - start).total_seconds()))
    if not measured:
        return None
    measured.sort(key=lambda observation: observation[0])
    return statistics.median(delta for _, delta in measured[-k:])


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--sessions", type=int, default=5,
                   help="Window for time-to-resume median (default 5).")
    args = p.parse_args()
    if args.sessions < 1:
        p.error("--sessions must be positive")

    try:
        rules = count_active_rules()
        days = days_since_last_proposal_closed()
        ttr = median_time_to_resume(args.sessions)
    except (ValueError, OSError) as exc:
        print(f"brain snapshot unavailable: {exc}", file=sys.stderr)
        return 2

    print(f"# Brain snapshot ({datetime.now(timezone.utc).isoformat(timespec='seconds')})")
    print()
    print(f"- **Active rules:** {rules}")
    if days is not None:
        print(f"- **Days since last proposal closed:** {days:.1f}")
    else:
        print(f"- **Days since last proposal closed:** —")
    if ttr is not None:
        if ttr < 60:
            ttr_str = f"{ttr:.0f}s"
        elif ttr < 3600:
            ttr_str = f"{ttr/60:.1f}m"
        else:
            ttr_str = f"{ttr/3600:.1f}h"
        print(f"- **Median recorded time-to-resume (last {args.sessions} measured sessions):** {ttr_str}")
    else:
        print("- **Median recorded time-to-resume:** — (no usable explicit session_start/task_start receipts)")
    print()
    print("_Recorded quantities only; proposal closure does not establish enactment or improvement._")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
