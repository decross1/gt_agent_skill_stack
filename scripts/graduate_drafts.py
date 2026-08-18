#!/usr/bin/env python3
"""graduate_drafts.py — dev-time scaffold for P-009 graduated autonomy.

Walks the bubbled-candidate (draft) lane of memory/brain/proposals.jsonl and
decides, per draft, whether it remains with a human:

    draft → blast_radius(first)
              high → leave for a human (logged "kept for human")
              low  → adversarial_gate(first) [advisory only]
                       any result → leave for a human

AUTHORITY BOUNDARY (read this before extending the file): there is no supported
automated verdict writer or attributable automated closed actor. This tool never
appends a promotion/verdict row, writes a handoff, or edits any framework file.
An adversarial signal may help a human decide, but is not authority to graduate
a draft. Enabling any automatic change is a separate, explicitly ratified design
and implementation effort.

This is a DEV-TIME tool. It is NOT part of the deterministic projection pipeline
and must NEVER be added to any projection guard / PROJECTION_SOURCES: the
adversarial gate (and brain_server.write_handoff, which synthesizes via an LLM)
may reach a model. The deterministic invariant covers the scanner / classifier /
ingest, not this scaffold.

The adversarial gate is STUBBED off this session (`return (False, …)`). Even a
test-monkeypatched pass cannot graduate a draft: the graduated path is closed
until a separately ratified attributable writer exists.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PROPOSALS = REPO / "memory" / "brain" / "proposals.jsonl"

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import project_summary as ps  # noqa: E402  (collapse_proposals + lifecycle_state)
from blast_radius import blast_radius  # noqa: E402


def adversarial_gate(first: dict) -> tuple[bool, str]:
    """STUB. The real gate is an LLM-using dev-time adversarial reviewer that
    tries to break a low-blast-radius candidate before human review.

    Until it exists it defaults closed. Even a future advisory pass is not an
    authority path for automated graduation."""
    return (False, "adversarial gate not yet implemented — defaults to human")


def graduate(apply: bool) -> list[dict]:
    """Classify every draft and retain it for human review.

    ``apply`` is retained only for CLI compatibility. It has no write path.
    """
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
        rec["decision"] = "kept for human"
        rec["why"] = ("adversarial gate passed, but automatic graduation is closed: "
                      "no supported attributable automated verdict writer")
        actions.append(rec)
    return actions


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Review low-blast-radius draft proposals (P-009). Automatic "
                    "graduation is closed; every draft remains human-gated.")
    grp = ap.add_mutually_exclusive_group()
    grp.add_argument("--dry-run", dest="apply", action="store_false",
                     help="print what each draft would do (default).")
    grp.add_argument("--apply", dest="apply", action="store_true",
                     help="compatibility flag; no promotion/write path exists.")
    ap.set_defaults(apply=False)
    args = ap.parse_args()

    actions = graduate(args.apply)
    mode = "APPLY" if args.apply else "DRY RUN"
    print(f"graduate_drafts — {mode} (automatic graduation CLOSED → promotes nothing)")
    drafts = len(actions)
    promoted = 0
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
