#!/usr/bin/env python3
"""watch_brain.py — keep the brain in sync with the apparatus, automatically.

Polls `a_bgt_rsi/{run_state,memory,logs}/*.jsonl` (and worktree logs) for
mtime/size changes. When something changes, debounces briefly to coalesce
rapid writes from a single iteration, then runs the dev-side pipeline:

    scripts/ingest_apparatus.py
    scripts/project_pages.py
    scripts/render_brain.py --day <today UTC>

Pure stdlib polling — no inotify, no watchfiles dep, portable.

The apparatus has no idea this exists. Watcher reads the apparatus's JSONL
files only; the brain firewall (apparatus never reads from brain) is preserved.

Run modes:
  --once         run one pipeline pass and exit (handy for cron / manual)
  (no flags)     daemon: poll forever, log to stdout (the lifecycle wrapper
                 nohups this and redirects stdout to a log file)
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CONSUMER = REPO.parent / "a_bgt_rsi"
INGEST = REPO / "scripts" / "ingest_apparatus.py"
PROJECT_PAGES = REPO / "scripts" / "project_pages.py"
RENDER_BRAIN = REPO / "scripts" / "render_brain.py"

# Directories to watch. Globs run relative to each.
WATCH_DIRS = (
    CONSUMER / "run_state",
    CONSUMER / "memory",
    CONSUMER / "logs",
)
# Also pick up worktree logs (see ingest_apparatus.py's logic) so off-main work
# is observed.
WORKTREE_LOG_GLOB = ".claude/worktrees/*/logs"


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _log(msg: str) -> None:
    # Single-line, ISO-stamped. Unbuffered so `tail -F` is responsive.
    print(f"[{_ts()}] {msg}", flush=True)


def collect_jsonl_signatures() -> dict[str, tuple[int, int]]:
    """Map of jsonl path -> (size, mtime_ns). Used to detect any change."""
    sigs: dict[str, tuple[int, int]] = {}
    paths: list[Path] = []
    for d in WATCH_DIRS:
        if d.is_dir():
            paths.extend(d.glob("*.jsonl"))
    for wt_logs in CONSUMER.glob(WORKTREE_LOG_GLOB):
        if wt_logs.is_dir():
            paths.extend(wt_logs.glob("*.jsonl"))
    for p in paths:
        try:
            st = p.stat()
            sigs[str(p)] = (st.st_size, st.st_mtime_ns)
        except FileNotFoundError:
            continue
    return sigs


def diff_signatures(
    prev: dict[str, tuple[int, int]],
    curr: dict[str, tuple[int, int]],
) -> list[str]:
    """Return paths that appeared, disappeared, grew, or were touched."""
    changed = []
    for path, sig in curr.items():
        if prev.get(path) != sig:
            changed.append(path)
    for path in prev:
        if path not in curr:
            changed.append(path)
    return changed


def run_step(cmd: list[str], label: str) -> tuple[bool, str]:
    """Run one pipeline step. Return (ok, last_line_of_output)."""
    try:
        result = subprocess.run(
            cmd,
            cwd=REPO,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        return False, f"{label}: TIMEOUT after 120s"
    out = (result.stdout or "").strip().splitlines()
    err = (result.stderr or "").strip().splitlines()
    tail = (out[-1] if out else "") or (err[-1] if err else "")
    if result.returncode != 0:
        return False, f"{label}: exit {result.returncode} — {tail}"
    return True, f"{label}: {tail}"


def run_pipeline(verbose: bool = False) -> bool:
    """Run ingest → project_pages → render_brain. Return True if all steps succeed."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    steps = [
        ([sys.executable, str(INGEST)], "ingest"),
        ([sys.executable, str(PROJECT_PAGES)], "project_pages"),
        ([sys.executable, str(RENDER_BRAIN), "--day", today], "render_brain"),
    ]
    all_ok = True
    for cmd, label in steps:
        ok, line = run_step(cmd, label)
        if not ok:
            _log(f"FAIL {line}")
            all_ok = False
            break
        if verbose:
            _log(f"  {line}")
    return all_ok


def daemon_loop(interval: float, debounce: float, verbose: bool) -> int:
    """Poll-and-fire main loop. Runs until SIGINT/SIGTERM."""
    _log(
        f"watch_brain starting — interval={interval}s debounce={debounce}s "
        f"dirs={[str(d.relative_to(CONSUMER.parent)) for d in WATCH_DIRS]}"
    )
    prev_sigs = collect_jsonl_signatures()
    _log(f"baseline: watching {len(prev_sigs)} jsonl files")

    pending_since: float | None = None

    try:
        while True:
            time.sleep(interval)
            curr_sigs = collect_jsonl_signatures()
            changed = diff_signatures(prev_sigs, curr_sigs)

            if changed and pending_since is None:
                # First detection of a change burst.
                names = ", ".join(sorted({Path(p).name for p in changed})[:6])
                _log(f"change detected ({len(changed)} files): {names} — debouncing")
                pending_since = time.monotonic()
                prev_sigs = curr_sigs
                continue

            if changed and pending_since is not None:
                # More changes during the debounce window — reset the timer.
                pending_since = time.monotonic()
                prev_sigs = curr_sigs
                continue

            if pending_since is not None and (time.monotonic() - pending_since) >= debounce:
                # Quiet for debounce seconds — fire the pipeline.
                pending_since = None
                t0 = time.monotonic()
                ok = run_pipeline(verbose=verbose)
                dt = time.monotonic() - t0
                _log(f"pipeline {'ok' if ok else 'FAIL'} in {dt:.1f}s")
                # Re-snapshot so the pipeline's own writes (if any) don't retrigger.
                prev_sigs = collect_jsonl_signatures()
    except KeyboardInterrupt:
        _log("interrupted — exiting")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run pipeline once and exit (skip the watch loop).",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Poll interval in seconds (default: 1.0).",
    )
    parser.add_argument(
        "--debounce",
        type=float,
        default=1.5,
        help="Quiet period after last change before firing (default: 1.5).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Log each pipeline step's tail line, not just summary.",
    )
    args = parser.parse_args()

    if not INGEST.exists() or not PROJECT_PAGES.exists() or not RENDER_BRAIN.exists():
        _log(
            f"error: one of the pipeline scripts is missing under {REPO / 'scripts'}"
        )
        return 2

    if args.once:
        _log("--once mode")
        ok = run_pipeline(verbose=True)
        return 0 if ok else 1

    return daemon_loop(args.interval, args.debounce, args.verbose)


if __name__ == "__main__":
    sys.exit(main())
