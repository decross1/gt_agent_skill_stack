#!/usr/bin/env python3
"""Blessed CLI for recording a human verdict on a brain proposal.

The brain UI's Accept / Reject buttons exec THIS via argv (no shell) — the
D-046 human-write-back pattern (UI POSTs exec blessed CLIs; out-of-enum exits
nonzero and writes nothing). It is also runnable from a terminal.

It records the governed *verdict* (append-only) — it does NOT enact the change.
Enacting a skill/rule edit is a separate dev-session / handoff step. A human
accepting a skill/rule proposal IS the human-review authority path of the
review-proposal skill; agents still use the auto-reject fast-path. The verdict
is stamped with the actor (default `human:ui`) and is fully auditable.

Exit codes: 0 ok · 2 bad proposal_id · 3 unknown proposal · 4 already decided
· 5 missing note · 6 io error · 7 corrupt ledger.

All exits print a single-line JSON object so the calling UI can parse the
outcome deterministically; nothing is written unless the verdict is recorded.
"""
import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROPOSALS = ROOT / "memory" / "brain" / "proposals.jsonl"

# frozen enum: CLI arg -> recorded verdict
VERDICTS = {"accept": "accepted", "reject": "rejected", "needs_revision": "human-review"}
PID_RE = re.compile(r"^P-\d+$")


def load_rows() -> list[dict]:
    """Parse proposals.jsonl into a list of records. A corrupt line is a
    fail-closed condition (ValueError) — the caller must refuse to record a
    verdict against a ledger it cannot fully read, rather than silently skip it."""
    if not PROPOSALS.exists():
        return []
    return [json.loads(l) for l in PROPOSALS.read_text().splitlines() if l.strip()]


def history(rows: list[dict], pid: str) -> list[dict]:
    return sorted((r for r in rows if r.get("proposal_id") == pid),
                  key=lambda x: x.get("timestamp", ""))


def main() -> None:
    ap = argparse.ArgumentParser(description="Record a human verdict on a brain proposal.")
    ap.add_argument("--proposal-id", required=True)
    ap.add_argument("--verdict", required=True, choices=sorted(VERDICTS))
    ap.add_argument("--note", default="", help="decision reasoning — required to reject/needs_revision (a rejection without a reason is an opinion); optional for accept (the human is the authority)")
    ap.add_argument("--agent", default="human:ui")
    ap.add_argument("--basis", default="original", choices=("original", "amended"),
                    help="which draft the verdict governs: the original proposal or the synthesized amended draft")
    a = ap.parse_args()

    if not PID_RE.match(a.proposal_id):
        print(json.dumps({"ok": False, "error": "bad proposal_id (want P-NNN)"}))
        sys.exit(2)
    if a.verdict != "accept" and not a.note.strip():
        print(json.dumps({"ok": False, "error": "note (reason) required to reject/needs_revision"}))
        sys.exit(5)

    try:
        rows = load_rows()
    except (ValueError, OSError) as e:
        # Fail closed: do not record a verdict against an unreadable ledger.
        print(json.dumps({"ok": False, "error": f"corrupt ledger: {e}"}))
        sys.exit(7)
    hist = history(rows, a.proposal_id)
    if not hist:
        print(json.dumps({"ok": False, "error": "unknown proposal"}))
        sys.exit(3)
    current = hist[-1].get("verdict") or "open"
    if current not in ("open", "human-review"):
        print(json.dumps({"ok": False, "error": f"already {current}"}))
        sys.exit(4)

    verdict = VERDICTS[a.verdict]
    out = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "proposal_id": a.proposal_id,
        "supersedes_proposal_id": a.proposal_id,
        "agent_id": a.agent,
        "verdict": verdict,
        "verdict_reasoning": a.note.strip(),
        "basis": a.basis,
        "rule_cited": None,
        "decision_id": None,
        "status": "human-review" if verdict == "human-review" else "closed",
    }
    try:
        with PROPOSALS.open("a") as f:
            f.write(json.dumps(out) + "\n")
    except OSError as e:
        print(json.dumps({"ok": False, "error": f"io: {e}"}))
        sys.exit(6)
    print(json.dumps({"ok": True, "recorded": verdict, "proposal_id": a.proposal_id}))


if __name__ == "__main__":
    main()
