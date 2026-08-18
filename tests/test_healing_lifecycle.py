#!/usr/bin/env python3
"""Truthfulness tests for accepted → enacted → verified proposal evidence."""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import project_summary as ps  # noqa: E402
import proposal_health as ph  # noqa: E402


SHA_A = "a" * 40
SHA_B = "b" * 40
OUTPUT_SHA = "c" * 64
SKILL_PATH = ".agents/skills/validate/SKILL.md"


def _proposal(*rows):
    return {"first": rows[0], "latest": rows[-1], "lifecycle": list(rows)}


OPEN = {
    "timestamp": "2026-08-01T00:00:00Z", "proposal_id": "P-900",
    "agent_id": "claude-code-main", "status": "open", "target_type": "skill",
    "target": "validate", "title": "Tighten validate", "change": "x",
}
ACCEPTED = {
    "timestamp": "2026-08-02T00:00:00Z", "proposal_id": "P-900",
    "agent_id": "human:decross1", "status": "closed", "verdict": "accepted",
}


def test_accepted_without_patch_is_pending_not_healed(monkeypatch):
    """A decision alone cannot produce an enacted, verified, or healed claim."""
    monkeypatch.setattr(ps, "skill_born_date", lambda _name: None)
    proposal = _proposal(OPEN, ACCEPTED)
    lifecycle = ps.proposal_healing_state(proposal)
    assert lifecycle["accepted"]["state"] == "accepted"
    assert lifecycle["enacted"]["state"] == "pending"
    assert lifecycle["verified"]["state"] == "unknown"

    skills, _ = ps.build_skills(
        [{"name": "validate", "layer": "A", "pack": "core", "runtime_safe": "true"}],
        [], {}, {"P-900": proposal}, [], [], "2026-08-01", "2026-08-07",
    )
    governance = skills[0]["governance"]
    assert governance["healing"]["enacted"]["state"] == "pending"
    assert governance["healed"] is None
    assert governance["state"] != "healed"


def test_pre_accept_evidence_cannot_be_promoted_by_a_later_accept(monkeypatch):
    """Append order is authority: backdated evidence is never lifecycle proof."""
    monkeypatch.setattr(ps, "_commit_changed_paths", lambda _root, _sha: {SKILL_PATH})
    pre_accept = dict(
        OPEN, timestamp="2026-08-01T12:00:00Z",
        enactment={"commit": SHA_A, "paths": [SKILL_PATH]},
        verification={"commit": SHA_A, "command": "pytest -q", "result": "pass",
                      "output_sha256": OUTPUT_SHA},
    )
    lifecycle = ps.proposal_healing_state(_proposal(OPEN, pre_accept, ACCEPTED))
    assert lifecycle["accepted"]["state"] == "accepted"
    assert lifecycle["enacted"]["state"] == "pending"
    assert lifecycle["verified"]["state"] == "unknown"


def test_exact_enactment_and_verification_requirements_fail_closed(monkeypatch):
    """Malformed paths, a commit mismatch, or an incomplete check never advance."""
    monkeypatch.setattr(ps, "_commit_changed_paths", lambda _root, _sha: {SKILL_PATH})

    missing_path = {"timestamp": "2026-08-03T00:00:00Z", "proposal_id": "P-900",
                    "status": "enacted", "enactment": {"commit": SHA_A}}
    assert ps.proposal_healing_state(_proposal(OPEN, ACCEPTED, missing_path))["enacted"]["state"] == "pending"

    enacted = {"timestamp": "2026-08-03T00:00:00Z", "proposal_id": "P-900",
               "status": "enacted",
               "enactment": {"commit": SHA_A, "paths": [SKILL_PATH]}}
    wrong_verification = {
        "timestamp": "2026-08-04T00:00:00Z", "proposal_id": "P-900", "status": "verified",
        "verification": {"commit": SHA_B, "command": "pytest -q", "result": "pass",
                         "output_sha256": OUTPUT_SHA},
    }
    lifecycle = ps.proposal_healing_state(_proposal(OPEN, ACCEPTED, enacted,
                                                     wrong_verification))
    assert lifecycle["enacted"]["state"] == "enacted"
    assert lifecycle["verified"]["state"] == "pending"

    verified = {
        "timestamp": "2026-08-05T00:00:00Z", "proposal_id": "P-900", "status": "verified",
        "verification": {"commit": SHA_A, "command": "pytest -q", "result": "pass",
                         "output_sha256": OUTPUT_SHA},
    }
    lifecycle = ps.proposal_healing_state(_proposal(OPEN, ACCEPTED, enacted, verified))
    assert lifecycle["verified"]["state"] == "verified"


def test_skill_enactment_rejects_an_unrelated_commit_even_after_accept(monkeypatch):
    """A README patch cannot enact a proposal whose target is `validate`."""
    unrelated = "README.md"
    monkeypatch.setattr(ps, "_commit_changed_paths", lambda _root, _sha: {unrelated})
    claimed = {
        "timestamp": "2026-08-03T00:00:00Z", "proposal_id": "P-900", "status": "enacted",
        "enactment": {"commit": SHA_A, "paths": [unrelated]},
    }
    lifecycle = ps.proposal_healing_state(_proposal(OPEN, ACCEPTED, claimed))
    assert lifecycle["enacted"]["state"] == "pending"
    assert lifecycle["verified"]["state"] == "unknown"


def test_commit_message_only_is_not_enactment_or_verification(tmp_path, monkeypatch, capsys):
    """A grep hit is surfaced as a hint but cannot close either evidence gate."""
    proposals = tmp_path / "memory" / "brain" / "proposals.jsonl"
    proposals.parent.mkdir(parents=True)
    proposals.write_text("\n".join(json.dumps(row) for row in (OPEN, ACCEPTED)) + "\n")
    monkeypatch.setattr(ph, "find_commits", lambda _root, _pid: ["deadbeef"])
    monkeypatch.setattr(sys, "argv", ["proposal_health.py", "--repo-root", str(tmp_path)])

    assert ph.main() == 1  # accepted but no exact enactment evidence
    report = capsys.readouterr().out
    assert "| P-900 | accepted" in report
    assert "| accepted | pending | unknown |" in report
    assert "unlinked commit-message mentions (not enactment evidence): P-900" in report
    assert "accepted-without-exact-enactment" in report
