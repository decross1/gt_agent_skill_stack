#!/usr/bin/env python3
"""scan_drift.py — the deterministic drift detector: read run logs, derive
machine-detected drift signals, append them to memory/brain/drift_signals.jsonl.

WHY THIS EXISTS
---------------
Detection used to be a once-per-session, judgment-driven `harvest` — an agent
read the consumer trace and classified findings into memory/feedback.jsonl. This
script is the *machine* "detected" lane: a stdlib, file->file pass that runs on
every apparatus change and derives drift signals with ZERO judgment — no LLM, no
network, fully reproducible from the run logs alone. It is the upstream source
the bubbler (draft_proposals.py) turns into DRAFT proposals.

It is deliberately separate from harvest: feedback.jsonl stays the curated
human/agent-judgment harvest ledger that drives conformance/hardening, and this
automation NEVER writes to it. The two ledgers do not muddy each other.

WHAT IT EMITS
-------------
For each NEW signal it appends one JSON object to memory/brain/drift_signals.jsonl
(SHARED schema — see ingest_apparatus.py for the source="runtime" rows):

    {"timestamp", "signal_id":"DS-0001", "source":"scan",
     "detector":"runlog_schema",
     "skill", "status_observed", "ref":"<label>:L<n>",
     "severity":"low"|"high", "evidence", "scope":"framework"}

signal_id is sequential, zero-padded to 4 (DS-0001), minted continuing from the
highest DS integer already in the ledger.

DETECTORS (deterministic, no judgment)
--------------------------------------
- runlog_failure: RETIRED 2026-06-28 (north-star Option 3, DECISIONS 2026-06-28).
  A run-log *outcome* is not drift evidence. A verdict-rendering skill recording
  'failed' (validate refusing to coerce a near-miss; gate-check halting at a gate;
  repro-check failing a check; code-review rejecting a diff) — or any skill
  recording aborted/escalated — is usually the skill WORKING, not malfunctioning.
  Inferring skill drift from a step's outcome produced only false positives
  (validate's honest FAIL verdicts on `lit_battery_post_t1_final` / `d050-decision-run`
  read as drift). Drift now comes from TWO trustworthy sources only: the apparatus
  *deliberately self-reporting* misuse/friction/gap (source="runtime", projected by
  ingest_apparatus.py) and FR-003 *schema violations* (runlog_schema, below). The
  function is left defined-but-uncalled as the seam — mirrors draft_proposals'
  retired runlog_signals().

- runlog_schema: scans ONLY the framework run log (FW_RUN). This is the
  low-noise scoping choice: the consumer apparatus may legitimately use an
  extended status vocabulary (its own run log is its own contract), so deciding
  whether a non-enum consumer status is real drift is a judgment call left to
  harvest — NOT something this deterministic detector should flag. Inside the
  FRAMEWORK's own run log, however, the FR-003 status enum is authoritative, so
  a non-empty status outside
  {started, passed, partial_pass, failed, aborted, halted, escalated, skipped}
  is a discipline flag. It yields a signal: skill="run-log", severity low,
  evidence quotes the offending status + task.

- runtime_selfreport: STUB returning []. Runtime skill-signals (source="runtime")
  are projected straight into drift_signals.jsonl by ingest_apparatus.py, so
  there is nothing for the scanner to *derive* from them here yet. The function
  exists as the seam for any future scan-side derivation over runtime rows.

IDEMPOTENCY
-----------
existing_signals() reads drift_signals.jsonl and returns
({(detector, ref)}, max DS int). A candidate whose (detector, ref) already
exists is skipped; new ids continue sequentially from the max. A second run
produces no duplicates.

DESIGN INVARIANTS HONORED
-------------------------
- Deterministic: stdlib only, file->file, NO LLM and NO network.
- Brain firewall: the consumer (a_bgt_rsi) is read READ-ONLY; this script only
  APPENDS to a framework-side ledger, never writes into the consumer.
- Append-only: drift_signals.jsonl is only ever appended to, never rewritten.
- Reuses draft_proposals' loaders so detection logic stays single-sourced.

CLI
---
    python3 scripts/scan_drift.py            # --dry-run (default): print
    python3 scripts/scan_drift.py --apply    # actually append signals

Stdlib-only. py_compile clean.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

# Reuse the loaders/constants from the bubbler so detection logic is single-sourced.
from draft_proposals import (  # noqa: E402
    jsonl,
    jsonl_numbered,
    framework_skills,
    resolve_consumer,
    FAILURE_STATUSES,
    FW_RUN,
    _trim,
)

DRIFT_SIGNALS = ROOT / "memory" / "brain" / "drift_signals.jsonl"

# Match the compact serialization the other brain ledgers use so rows are
# byte-compatible with the file.
_SEP = (",", ":")

SCAN_SOURCE = "scan"
SCOPE = "framework"

# The FR-003 run-log status enum. A framework run-log status outside this set is
# a schema-discipline flag (runlog_schema detector).
RUNLOG_STATUS_ENUM = {
    "started", "passed", "partial_pass", "failed",
    "aborted", "halted", "escalated", "skipped",
}
# Failure-ish statuses that escalate a runlog_failure signal to high severity.
HIGH_FAILURE_STATUSES = {"aborted", "escalated"}


# ---------------------------------------------------------------------------
# Detectors (deterministic, no judgment, no LLM)
# ---------------------------------------------------------------------------

def runlog_failure(skills: set[str], consumer: Path | None) -> list[dict]:
    """RETIRED 2026-06-28 (Option 3) — NOT called by build_signals(). A run-log
    outcome is not drift evidence: a verdict-rendering skill's honest FAIL is the
    skill working, not drifting, and inferring drift from a step's status produced
    only false positives. Left defined-but-uncalled as the seam. Original behavior:
    one candidate per run-log row with skill_used on a framework skill AND a
    failure-ish status, across the framework run log and (read-only) the
    consumer's run log if reachable."""
    out: list[dict] = []
    logs: list[tuple[str, Path]] = [("framework.run.jsonl", FW_RUN)]
    if consumer is not None:
        logs.append(("a_bgt_rsi/week1.run.jsonl",
                     consumer / "run_state" / "week1.run.jsonl"))
    for label, path in logs:
        for ln, o in jsonl_numbered(path):
            skill = (o.get("skill_used") or "").strip()
            status = (o.get("status") or "").strip()
            if skill not in skills or status not in FAILURE_STATUSES:
                continue
            task = (o.get("task_id") or "(untitled step)").strip()
            severity = "high" if status in HIGH_FAILURE_STATUSES else "low"
            evidence = _trim(
                f"[[{skill}]] ran '{status}' on task '{task}' in {label}.", 200)
            out.append({
                "detector": "runlog_failure",
                "skill": skill,
                "status_observed": status,
                "ref": f"{label}:L{ln}",
                "severity": severity,
                "evidence": evidence,
            })
    return out


def runlog_schema(skills: set[str]) -> list[dict]:
    """One candidate per FRAMEWORK run-log row whose status is non-empty and
    outside the FR-003 enum.

    Framework-only by design: the consumer apparatus owns its own run-log
    contract and may use an extended status vocabulary, so judging a non-enum
    consumer status is left to harvest. Inside the framework's own run log the
    FR-003 enum is authoritative, so a non-enum status is a deterministic
    schema-discipline flag attributed to the [[run-log]] skill."""
    out: list[dict] = []
    for ln, o in jsonl_numbered(FW_RUN):
        status = (o.get("status") or "").strip()
        if not status or status in RUNLOG_STATUS_ENUM:
            continue
        task = (o.get("task_id") or "(untitled step)").strip()
        evidence = _trim(
            f"framework.run.jsonl row used status '{status}' outside the "
            f"FR-003 enum on task '{task}'.", 200)
        out.append({
            "detector": "runlog_schema",
            "skill": "run-log",
            "status_observed": status,
            "ref": f"framework.run.jsonl:L{ln}",
            "severity": "low",
            "evidence": evidence,
        })
    return out


def runtime_selfreport(skills: set[str]) -> list[dict]:
    """STUB. Runtime skill-signals (source="runtime") are projected directly
    into drift_signals.jsonl by ingest_apparatus.py — the scanner does not need
    to derive anything from them, so this returns []. The seam exists for any
    future scan-side derivation over runtime rows."""
    return []


# ---------------------------------------------------------------------------
# Existing-signal state (idempotency)
# ---------------------------------------------------------------------------

def existing_signals() -> tuple[set[tuple[str, str]], int]:
    """Returns:
      keys     {(detector, ref)} already present in drift_signals.jsonl — the
               scan idempotency key.
      max_num  highest DS-NNNN integer seen (0 when none) — next id base.
    """
    keys: set[tuple[str, str]] = set()
    max_num = 0
    for r in jsonl(DRIFT_SIGNALS):
        sid = r.get("signal_id") or ""
        if sid.startswith("DS-"):
            try:
                max_num = max(max_num, int(sid[3:]))
            except ValueError:
                pass
        detector = (r.get("detector") or "").strip()
        ref = (r.get("ref") or "").strip()
        if detector and ref:
            keys.add((detector, ref))
    return keys, max_num


# ---------------------------------------------------------------------------
# Build signal entries (assign sequential ids, dedup against existing signals)
# ---------------------------------------------------------------------------

def build_signals() -> tuple[list[dict], list[dict]]:
    """Returns (new_signals, skipped) — skipped carries {detector, ref, reason}
    so the summary can explain idempotency no-ops."""
    skills = framework_skills()
    keys, max_num = existing_signals()

    # runlog_failure RETIRED (Option 3, 2026-06-28): a run-log outcome is not
    # drift evidence. Drift = FR-003 schema violations (runlog_schema) + the
    # apparatus's deliberate self-reports (projected into drift_signals.jsonl by
    # ingest_apparatus.py with source="runtime"; runtime_selfreport stays a stub).
    candidates = (runlog_schema(skills)
                  + runtime_selfreport(skills))

    new_signals: list[dict] = []
    skipped: list[dict] = []
    minted_keys: set[tuple[str, str]] = set()
    ts = _now()
    n = max_num
    for c in candidates:
        key = (c["detector"], c["ref"])
        if key in keys or key in minted_keys:
            skipped.append({"detector": c["detector"], "ref": c["ref"],
                            "reason": "already detected"})
            continue
        minted_keys.add(key)
        n += 1
        new_signals.append({
            "timestamp": ts,
            "signal_id": f"DS-{n:04d}",
            "source": SCAN_SOURCE,
            "detector": c["detector"],
            "skill": c["skill"],
            "status_observed": c["status_observed"],
            "ref": c["ref"],
            "severity": c["severity"],
            "evidence": c["evidence"],
            "scope": SCOPE,
        })
    return new_signals, skipped


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Emit + CLI
# ---------------------------------------------------------------------------

def append_signals(rows: list[dict]) -> None:
    with DRIFT_SIGNALS.open("a") as f:
        for r in rows:
            f.write(json.dumps(r, separators=_SEP, ensure_ascii=False) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Deterministically scan run logs for drift and append "
                    "signals to memory/brain/drift_signals.jsonl (source=scan).")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", default=True,
                      help="print what would be added; write nothing (default).")
    mode.add_argument("--apply", action="store_true",
                      help="actually append the drift signals.")
    args = ap.parse_args()
    apply = bool(args.apply)

    new_signals, skipped = build_signals()

    print("scan_drift — deterministic drift detection (run logs -> drift_signals)")
    print(f"  signals file: {DRIFT_SIGNALS}")
    print(f"  candidates: {len(new_signals) + len(skipped)}  "
          f"new: {len(new_signals)}  already-detected (skipped): {len(skipped)}")
    for d in new_signals:
        print(f"  + {d['signal_id']}  {d['detector']}  skill:{d['skill']}  "
              f"[{d['severity']}]  <- {d['ref']}")
        print(f"      {d['evidence']}")
    if not new_signals:
        print("  (no new drift signals detected)")

    if apply:
        if new_signals:
            append_signals(new_signals)
            print(f"  APPLIED — appended {len(new_signals)} signal(s) "
                  f"with source='{SCAN_SOURCE}'.")
        else:
            print("  APPLIED — nothing to append.")
    else:
        print("  DRY RUN — nothing written. Re-run with --apply to append.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
