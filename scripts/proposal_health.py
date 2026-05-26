#!/usr/bin/env python3
"""
N2 — proposal-health report.

Reads `memory/brain/proposals.jsonl` and checks whether the
harvest → propose → review → implementation loop is closing.

Per proposal: filed-at, days-open OR days-to-verdict, verdict, rule_cited,
commit-ref via `git log --grep P-NNN`. Stdout-only; no on-disk state.

Falsifiable kill switch (from session plan):
  - if accepted-but-uncommitted > 50%, the loop is broken
  - if any auto-reject lacks a rule citation, the loop is broken

Usage: python scripts/proposal_health.py [--repo-root PATH]
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
from datetime import datetime, timezone
from pathlib import Path

CLOSED_VERDICTS = {"accepted", "auto-accept", "auto-reject"}
OPEN_VERDICTS = {"human-review", None, ""}


def parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def load_proposals(path: Path) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {}
    with path.open() as fp:
        for line in fp:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            pid = row.get("proposal_id")
            if not pid:
                continue
            groups.setdefault(pid, []).append(row)
    for pid, rows in groups.items():
        rows.sort(key=lambda r: r.get("timestamp", ""))
    return groups


def find_commits(repo_root: Path, pid: str) -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(repo_root), "log", "--all", "--format=%h", f"--grep={pid}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if out.returncode != 0:
        return []
    return [s for s in out.stdout.strip().splitlines() if s]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parent.parent),
        help="Path to the framework repo (default: parent of scripts/).",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root)
    proposals_path = repo_root / "memory" / "brain" / "proposals.jsonl"
    if not proposals_path.exists():
        print(f"error: {proposals_path} not found")
        return 2

    groups = load_proposals(proposals_path)
    now = datetime.now(timezone.utc)

    rows = []
    for pid in sorted(groups):
        entries = groups[pid]
        first = entries[0]
        latest = entries[-1]
        first_ts = parse_ts(first["timestamp"])
        latest_ts = parse_ts(latest["timestamp"])
        verdict = latest.get("verdict")
        title = (first.get("title") or "").strip()

        is_closed = verdict in CLOSED_VERDICTS
        if is_closed:
            days_metric = (latest_ts - first_ts).total_seconds() / 86400.0
            days_label = "days→verdict"
        else:
            days_metric = (now - first_ts).total_seconds() / 86400.0
            days_label = "days open"

        rule_cited = latest.get("rule_cited") or first.get("rule_cited") or ""
        commits: list[str] = []
        if verdict in {"accepted", "auto-accept"}:
            commits = find_commits(repo_root, pid)

        rows.append(
            {
                "pid": pid,
                "title": title,
                "verdict": verdict or "open",
                "days_metric": days_metric,
                "days_label": days_label,
                "rule_cited": rule_cited,
                "commits": commits,
                "is_closed": is_closed,
            }
        )

    # ---- table ----
    print("# Proposal health\n")
    print(f"_As of {now.isoformat(timespec='seconds')}_\n")
    print("| ID | Verdict | Days | Rule | Commit | Title |")
    print("|---|---|---:|---|---|---|")
    for r in rows:
        commit_cell = ", ".join(r["commits"]) if r["commits"] else "—"
        rule_cell = r["rule_cited"] if r["rule_cited"] else "—"
        title = r["title"][:60] + ("…" if len(r["title"]) > 60 else "")
        title = title.replace("|", "\\|")
        print(
            f"| {r['pid']} | {r['verdict']} | {r['days_metric']:.1f} ({r['days_label']}) "
            f"| {rule_cell} | {commit_cell} | {title} |"
        )

    # ---- summary ----
    print("\n## Summary\n")
    by_verdict: dict[str, int] = {}
    for r in rows:
        by_verdict[r["verdict"]] = by_verdict.get(r["verdict"], 0) + 1
    for v in sorted(by_verdict):
        print(f"- {v}: {by_verdict[v]}")

    open_days = [r["days_metric"] for r in rows if not r["is_closed"]]
    closed_days = [r["days_metric"] for r in rows if r["is_closed"]]
    if open_days:
        print(f"- median days open (open proposals): {statistics.median(open_days):.1f}")
    if closed_days:
        print(
            f"- median days→verdict (closed proposals): "
            f"{statistics.median(closed_days):.1f}"
        )

    accepted = [
        r for r in rows if r["verdict"] in {"accepted", "auto-accept"}
    ]
    uncommitted = [r for r in accepted if not r["commits"]]
    if accepted:
        share = 100.0 * len(uncommitted) / len(accepted)
        print(
            f"- accepted-but-uncommitted: {len(uncommitted)} / {len(accepted)} "
            f"({share:.0f}%)"
        )
        if uncommitted:
            print("  - " + ", ".join(r["pid"] for r in uncommitted))

    rejects = [r for r in rows if r["verdict"] == "auto-reject"]
    unciited = [r for r in rejects if not r["rule_cited"]]
    if rejects:
        print(
            f"- auto-rejects without rule citation: "
            f"{len(unciited)} / {len(rejects)}"
        )
        if unciited:
            print("  - " + ", ".join(r["pid"] for r in unciited))

    # ---- kill-switch verdict ----
    print("\n## Kill-switch check\n")
    fail = False
    if accepted:
        share = 100.0 * len(uncommitted) / len(accepted)
        if share > 50.0:
            print(f"- FAIL: accepted-but-uncommitted = {share:.0f}% (>50%)")
            fail = True
        else:
            print(f"- PASS: accepted-but-uncommitted = {share:.0f}% (≤50%)")
    if unciited:
        print(f"- FAIL: {len(unciited)} auto-reject(s) missing rule citation")
        fail = True
    elif rejects:
        print(f"- PASS: all {len(rejects)} auto-reject(s) cite a rule")

    print()
    print("KILL-SWITCH: " + ("TRIGGERED" if fail else "clear"))
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
