#!/usr/bin/env python3
"""
N2 — proposal-health report.

Reads `memory/brain/proposals.jsonl` and checks whether the
harvest → propose → review → implementation loop is closing.

Per proposal: filed-at, days-open OR days-to-verdict, verdict, rule_cited, and
the distinct accepted / enacted / verified states.  A `git log --grep P-NNN`
match is reported only as an unlinked discovery hint: it is never enactment or
verification evidence. Stdout-only; no on-disk state.

Falsifiable kill switch (from session plan, tightened to exact evidence):
  - if accepted-without-exact-enactment > 50%, the loop is broken
  - if any auto-reject lacks a rule citation, the loop is broken

Usage: python scripts/proposal_health.py [--repo-root PATH]
"""

from __future__ import annotations

import argparse
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import project_summary as ps  # noqa: E402  (shared deterministic lifecycle)
from brain_ledger import ProposalLedgerError, read_proposals  # noqa: E402

CLOSED_VERDICTS = {"accepted", "auto-accept", "auto-reject"}
OPEN_VERDICTS = {"human-review", None, ""}


def parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def load_proposals(path: Path) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {}
    for row in read_proposals(path, quarantine_known_legacy=True):
        pid = row["proposal_id"]
        groups.setdefault(pid, []).append(row)
    for pid, rows in groups.items():
        rows.sort(key=lambda r: r.get("timestamp", ""))
    return groups


def find_commits(repo_root: Path, pid: str) -> list[str]:
    """Return subject matches as discovery hints, never lifecycle proof."""
    out = subprocess.run(
        ["git", "-C", str(repo_root), "log", "--all", "--format=%h", f"--grep={pid}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if out.returncode != 0:
        return []
    return [s for s in out.stdout.strip().splitlines() if s]


def proposal_state(entries: list[dict], repo_root: Path) -> dict:
    """Collapse one append-only proposal chain and fail closed via the projector."""
    proposal = {"first": entries[0], "latest": entries[-1], "lifecycle": entries}
    return ps.proposal_healing_state(proposal, repo_root)


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

    try:
        groups = load_proposals(proposals_path)
    except ProposalLedgerError as exc:
        print(f"error: proposal ledger is not safe to read: {exc}")
        return 2
    now = datetime.now(timezone.utc)

    rows = []
    for pid in sorted(groups):
        entries = groups[pid]
        first = entries[0]
        latest = entries[-1]
        first_ts = parse_ts(first["timestamp"])
        verdict = ps.final_verdict(
            {"first": first, "latest": latest, "lifecycle": entries}
        )
        verdict_row = next((row for row in reversed(entries) if row.get("verdict")), None)
        verdict_ts = parse_ts((verdict_row or latest)["timestamp"])
        title = (first.get("title") or "").strip()
        lifecycle = proposal_state(entries, repo_root)

        is_closed = verdict in CLOSED_VERDICTS
        if is_closed:
            days_metric = (verdict_ts - first_ts).total_seconds() / 86400.0
            days_label = "days→verdict"
        else:
            days_metric = (now - first_ts).total_seconds() / 86400.0
            days_label = "days open"

        rule_cited = ((verdict_row or {}).get("rule_cited")
                      or first.get("rule_cited") or "")
        commits: list[str] = []
        if verdict in {"accepted", "auto-accept"}:
            commits = find_commits(repo_root, pid)

        rows.append(
            {
                "pid": pid,
                "title": title,
                "verdict": verdict,
                "days_metric": days_metric,
                "days_label": days_label,
                "rule_cited": rule_cited,
                "commit_mentions": commits,
                "lifecycle": lifecycle,
                "is_closed": is_closed,
            }
        )

    # ---- table ----
    print("# Proposal health\n")
    print(f"_As of {now.isoformat(timespec='seconds')}_\n")
    print("| ID | Verdict | Days | Accepted | Enacted | Verified | Rule | Commit mention | Title |")
    print("|---|---|---:|---|---|---|---|---|---|")
    for r in rows:
        commit_cell = (", ".join(r["commit_mentions"])
                       if r["commit_mentions"] else "—")
        rule_cell = r["rule_cited"] if r["rule_cited"] else "—"
        title = r["title"][:60] + ("…" if len(r["title"]) > 60 else "")
        title = title.replace("|", "\\|")
        print(
            f"| {r['pid']} | {r['verdict']} | {r['days_metric']:.1f} ({r['days_label']}) "
            f"| {r['lifecycle']['accepted']['state']} "
            f"| {r['lifecycle']['enacted']['state']} "
            f"| {r['lifecycle']['verified']['state']} "
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
    unenacted = [r for r in accepted
                 if r["lifecycle"]["enacted"]["state"] != "enacted"]
    if accepted:
        share = 100.0 * len(unenacted) / len(accepted)
        print(
            f"- accepted-without-exact-enactment: {len(unenacted)} / {len(accepted)} "
            f"({share:.0f}%)"
        )
        if unenacted:
            print("  - " + ", ".join(r["pid"] for r in unenacted))
        mentions = [r for r in accepted if r["commit_mentions"]]
        if mentions:
            print("- unlinked commit-message mentions (not enactment evidence): "
                  + ", ".join(r["pid"] for r in mentions))

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
        share = 100.0 * len(unenacted) / len(accepted)
        if share > 50.0:
            print(f"- FAIL: accepted-without-exact-enactment = {share:.0f}% (>50%)")
            fail = True
        else:
            print(f"- PASS: accepted-without-exact-enactment = {share:.0f}% (≤50%)")
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
