#!/usr/bin/env python3
"""blast_radius.py — deterministic blast-radius classifier for a proposal.

Formalizes the allowlist the `review-proposal` skill applies by hand: a change is
either LOCALIZED (a brain-page / edge / backlink — append-only, reversible, no
governance reach) or it touches GOVERNANCE (a rule, a decision, a skill, or a
load-bearing root file). The P-009 graduated-autonomy path may only auto-promote
the localized class; everything that could change how the system governs itself —
or anything the classifier cannot positively place as localized — routes to a
human (conservative default).

Pure stdlib, file→file (it only greps SKILL.md frontmatter on disk). It NEVER
reaches an LLM; it is safe to call from any deterministic context.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from brain_ledger import ProposalLedgerError, read_proposals

REPO = Path(__file__).resolve().parent.parent
PROPOSALS = REPO / "memory" / "brain" / "proposals.jsonl"
SKILLS_DIR = REPO / ".agents" / "skills"

# target_type values that always reach governance.
HIGH_TYPES = {"rule", "decision", "skill"}
# target_type values that are localized, reversible brain content.
LOW_TYPES = {"brain-page", "page", "edge", "backlink"}
# load-bearing root files — editing any is a governance-level change.
HIGH_TARGETS = {"rules.md", "DECISIONS.md", "BOUNDARY.md", "install.sh"}


def _is_runtime_safe_core(skill: str) -> bool:
    """True when .agents/skills/<skill>/SKILL.md is frontmatter-marked
    `runtime-safe: true` (the runtime-safe core; see BOUNDARY.md). Absent file
    or unreadable → False (it simply isn't one of the known core skills)."""
    skill = (skill or "").strip()
    if not skill:
        return False
    md = SKILLS_DIR / skill / "SKILL.md"
    try:
        text = md.read_text()
    except OSError:
        return False
    return "runtime-safe: true" in text


def blast_radius(first: dict) -> str:
    """Classify a proposal's first row as "low" (localized, auto-promotable) or
    "high" (governance reach → human). Conservative: an unknown target_type is
    high, so a novel proposal shape can never be auto-promoted by default."""
    ttype = (first.get("target_type") or "").strip().lower()
    target = (first.get("target") or "").strip()

    if ttype in HIGH_TYPES:
        return "high"
    if target in HIGH_TARGETS:
        return "high"
    if _is_runtime_safe_core(target):
        return "high"
    if ttype in LOW_TYPES:
        return "low"
    return "high"  # conservative default — unknown goes to a human


# ---------------------------------------------------------------------------
# CLI (optional, manual use): print the classification for one proposal_id.
# ---------------------------------------------------------------------------

def _first_row(pid: str) -> dict | None:
    """Earliest (filed) row for a proposal_id from proposals.jsonl, by
    timestamp — the row blast_radius() classifies."""
    rows = [row for row in read_proposals(
        PROPOSALS, quarantine_known_legacy=True
    ) if row.get("proposal_id") == pid]
    if not rows:
        return None
    return min(rows, key=lambda r: r.get("timestamp", ""))


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Print the blast-radius classification (low|high) for a "
                    "proposal_id read from memory/brain/proposals.jsonl.")
    ap.add_argument("proposal_id", help="e.g. P-003")
    args = ap.parse_args()

    try:
        first = _first_row(args.proposal_id)
    except ProposalLedgerError as exc:
        print(json.dumps({"ok": False, "error": f"corrupt proposal ledger: {exc}"}))
        return 2
    if first is None:
        print(json.dumps({"ok": False, "error": "unknown proposal_id"}))
        return 3
    cls = blast_radius(first)
    print(json.dumps({
        "ok": True,
        "proposal_id": args.proposal_id,
        "target_type": first.get("target_type"),
        "target": first.get("target"),
        "blast_radius": cls,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
