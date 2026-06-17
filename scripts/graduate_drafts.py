#!/usr/bin/env python3
"""graduate_drafts.py — dev-time scaffold for P-009 graduated autonomy.

Walks the bubbled-candidate (draft) lane of memory/brain/proposals.jsonl and
decides, per draft, whether it may auto-promote into the open review queue:

    draft → blast_radius(first)
              high → leave for a human (logged "kept for human")
              low  → adversarial_gate(first)
                       passes → promote (append open row) + record verdict
                                via the blessed CLI + write the handoff
                       fails  → leave for a human

ENACTMENT BOUNDARY (read this before extending the file): the auto path stops at
RECORDING A VERDICT + WRITING A HANDOFF. It NEVER auto-edits SKILL.md, rules.md,
DECISIONS.md, or BOUNDARY.md — and blast_radius already routes all of those to
`high` (human) anyway. Turning auto-edit on is a separate, gated decision.

This is a DEV-TIME tool. It is NOT part of the deterministic projection pipeline
and must NEVER be added to any projection guard / PROJECTION_SOURCES: the
adversarial gate (and brain_server.write_handoff, which synthesizes via an LLM)
may reach a model. The deterministic invariant covers the scanner / classifier /
ingest, not this scaffold.

The adversarial gate is STUBBED off this session (`return (False, …)`), so a
full run promotes NOTHING — the scaffold is complete and runnable, but the
graduated path stays dark until the gate is real.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PROPOSALS = REPO / "memory" / "brain" / "proposals.jsonl"
REVIEW_CLI = REPO / "scripts" / "review_proposal_cli.py"

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import project_summary as ps  # noqa: E402  (collapse_proposals + lifecycle_state)
from blast_radius import blast_radius  # noqa: E402


def adversarial_gate(first: dict) -> tuple[bool, str]:
    """STUB. The real gate is an LLM-using dev-time adversarial reviewer that
    tries to break a low-blast-radius candidate before it auto-promotes.

    Until it exists it defaults closed → nothing graduates. Because it returns
    False, the promotion branch below is never taken this session."""
    return (False, "adversarial gate not yet implemented — defaults to human")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def promote_draft(pid: str, first: dict) -> dict:
    """Promote one draft to the open review queue, then record the graduated
    verdict and write the implementation handoff. Only ever called on a low
    blast-radius draft whose adversarial gate has PASSED.

    (a) append a promotion row (status='open') to proposals.jsonl — append-only,
        so the draft's latest row flips draft→open without a rewrite;
    (b) record a verdict via the blessed CLI (review_proposal_cli.py), the only
        sanctioned write-back channel for verdicts;
    (c) write the handoff (brain_server.write_handoff) — the dev brief; NO edit
        is applied here.
    """
    row = {
        "timestamp": _now(),
        "proposal_id": pid,
        "supersedes_proposal_id": pid,
        "agent_id": "auto:graduated",
        "status": "open",
    }
    with PROPOSALS.open("a") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")

    verdict = subprocess.run(
        [sys.executable, str(REVIEW_CLI),
         "--proposal-id", pid, "--verdict", "accept",
         "--note", "graduated: low-blast-radius, adversarial gate passed",
         "--agent", "auto:graduated", "--basis", "original"],
        capture_output=True, text=True, timeout=30)
    try:
        verdict_out = json.loads(verdict.stdout.strip() or "{}")
    except json.JSONDecodeError:
        verdict_out = {"ok": False, "error": verdict.stderr.strip() or "cli error"}
    verdict_out["exit_code"] = verdict.returncode

    # Imported late so a deterministic context never pulls brain_server (and its
    # LLM reach) into scope unless a promotion actually fires.
    import brain_server as bs  # noqa: E402
    handoff_path = bs.write_handoff(first)

    return {"promotion_row": row, "verdict": verdict_out,
            "handoff_path": handoff_path}


def graduate(apply: bool) -> list[dict]:
    """Classify every draft and (when --apply and the gate passes) promote it.
    Returns a per-draft action log."""
    proposals = ps.collapse_proposals(ps.load_jsonl(PROPOSALS))
    actions: list[dict] = []
    for pid, p in sorted(proposals.items()):
        if ps.lifecycle_state(p) != "draft":
            continue
        first = p["first"]
        radius = blast_radius(first)
        rec = {"proposal_id": pid, "blast_radius": radius,
               "title": first.get("title", "")}
        if radius == "high":
            rec["decision"] = "kept for human"
            rec["why"] = "high blast radius (governance reach)"
            actions.append(rec)
            continue
        passed, reason = adversarial_gate(first)
        if not passed:
            rec["decision"] = "kept for human"
            rec["why"] = f"adversarial gate did not pass: {reason}"
            actions.append(rec)
            continue
        rec["decision"] = "promote"
        if apply:
            rec["result"] = promote_draft(pid, first)
        else:
            rec["result"] = "would promote (dry-run)"
        actions.append(rec)
    return actions


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Graduate low-blast-radius draft proposals (P-009). The "
                    "adversarial gate is stubbed off — nothing promotes yet.")
    grp = ap.add_mutually_exclusive_group()
    grp.add_argument("--dry-run", dest="apply", action="store_false",
                     help="print what each draft would do (default).")
    grp.add_argument("--apply", dest="apply", action="store_true",
                     help="perform promotions (currently a no-op: gate stubbed False).")
    ap.set_defaults(apply=False)
    args = ap.parse_args()

    actions = graduate(args.apply)
    mode = "APPLY" if args.apply else "DRY RUN"
    print(f"graduate_drafts — {mode} (adversarial gate STUBBED → promotes nothing)")
    drafts = len(actions)
    promoted = sum(1 for a in actions if a["decision"] == "promote" and args.apply)
    kept = sum(1 for a in actions if a["decision"] == "kept for human")
    print(f"  drafts: {drafts}  kept for human: {kept}  promoted: {promoted}")
    for a in actions:
        print(f"  - {a['proposal_id']} [{a['blast_radius']}] {a['decision']}"
              f" — {a.get('why', a.get('title', ''))}")
    if not args.apply:
        print("DRY RUN — nothing written.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
