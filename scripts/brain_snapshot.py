#!/usr/bin/env python3
"""
N4 — brain-compounding snapshot.

Reads the brain to produce a 3-number snapshot of whether the framework is
getting better at remembering itself. Designed to be invoked once per
session at resume time by [[resume-state]].

Metrics:
  (a) active rules — count of FR-NNN/AR-NNN in memory/brain/rules.md
  (b) days since last human-review proposal closed
  (c) median time-to-resume — seconds from session start to first run-log
      entry (over the last K sessions)

If (a) grows session-over-session and (c) shrinks, the brain is
compounding. If neither shifts in 5 sessions, it isn't and we should
reconsider.

Usage: python scripts/brain_snapshot.py [--sessions 5]
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RULES_MD = REPO / "memory" / "brain" / "rules.md"
PROPOSALS = REPO / "memory" / "brain" / "proposals.jsonl"
FW_RUN = REPO / "run_state" / "framework.run.jsonl"

RULE_ID_RE = re.compile(r"^###\s+(FR-\d+|AR-\d+)\s+—", re.MULTILINE)


def parse_ts(s: str) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def count_active_rules() -> int:
    if not RULES_MD.exists():
        return 0
    text = RULES_MD.read_text()
    return len(RULE_ID_RE.findall(text))


def days_since_last_human_review() -> float | None:
    if not PROPOSALS.exists():
        return None
    closed_human_review: list[datetime] = []
    with PROPOSALS.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            # A "human-review" proposal that later got a non-human-review
            # verdict counts as closed at the later verdict's timestamp.
            if r.get("status") == "closed" and r.get("verdict") in {"accepted", "auto-accept", "auto-reject"}:
                ts = parse_ts(r.get("timestamp", ""))
                if ts:
                    closed_human_review.append(ts)
    if not closed_human_review:
        return None
    latest = max(closed_human_review)
    return (datetime.now(timezone.utc) - latest).total_seconds() / 86400.0


def median_time_to_resume(k: int) -> float | None:
    """Time between consecutive `s<N>_*` task-id session boundaries and the
    first non-`*_state_update` / `*_validate` task within that session.
    """
    if not FW_RUN.exists():
        return None
    sessions: dict[str, list[tuple[datetime, str]]] = {}
    with FW_RUN.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            tid = r.get("task_id") or ""
            ts = parse_ts(r.get("timestamp", ""))
            if not tid or not ts:
                continue
            # Session id from task prefix (s4, s4_1, s14_3, n2_..., s24a_...).
            m = re.match(r"(s\d+[a-z]?|n\d+)_", tid)
            sid = m.group(1) if m else tid.split("_", 1)[0]
            sessions.setdefault(sid, []).append((ts, tid))

    # For each session: time between first entry overall and first
    # non-resume/state-update entry. We treat the first task as "session
    # start", then look for the first non-bookkeeping task.
    deltas: list[float] = []
    for sid, entries in sessions.items():
        entries.sort()
        if len(entries) < 2:
            continue
        start_ts = entries[0][0]
        for ts, tid in entries[1:]:
            if "state_update" in tid or "validate" in tid or "resume" in tid:
                continue
            deltas.append((ts - start_ts).total_seconds())
            break
    if not deltas:
        return None
    # Latest k sessions only (chronologically by session-id order).
    deltas = deltas[-k:]
    return statistics.median(deltas)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--sessions", type=int, default=5,
                   help="Window for time-to-resume median (default 5).")
    args = p.parse_args()

    rules = count_active_rules()
    days = days_since_last_human_review()
    ttr = median_time_to_resume(args.sessions)

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
        print(f"- **Median time-to-resume (last {args.sessions} sessions):** {ttr_str}")
    else:
        print(f"- **Median time-to-resume:** — (insufficient data)")
    print()
    print("_Compounds if rules grow and time-to-resume shrinks across sessions._")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
