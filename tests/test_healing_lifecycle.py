#!/usr/bin/env python3
"""Truthfulness tests for accepted → enacted → verified proposal evidence."""
import copy
import json
import sys
from pathlib import Path

import pytest

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


@pytest.mark.parametrize("timestamp", [
    "not-a-time", "2026-02-30T12:00:00Z", "2026-09-05T25:00:00Z",
    "2026-09-05T12:00:00+01:99", "2026-09-05", "", None, 7, [], {},
    "2026-09-05T12:00:60Z", "2026-09-05T12:00:00+24:00",
    "2025-02-29T12:00:00Z",
])
def test_malformed_temporal_metadata_is_unknown_without_discarding_structure(monkeypatch, timestamp):
    monkeypatch.setattr(ps, "_commit_changed_paths", lambda _root, _sha: {SKILL_PATH})
    accepted = dict(ACCEPTED, timestamp=timestamp)
    enacted = {"timestamp": timestamp, "proposal_id": "P-900",
               "enactment": {"commit": SHA_A, "paths": [SKILL_PATH]}}
    claimed = {"timestamp": timestamp, "proposal_id": "P-900",
               "verification": {"commit": SHA_A, "command": "pytest -q",
                                "result": "pass", "output_sha256": OUTPUT_SHA}}
    proposal = _proposal(OPEN, accepted, enacted, claimed)
    original = copy.deepcopy(proposal)
    state = ps.proposal_healing_state(proposal)
    assert state["accepted"] == {"state": "accepted", "at": None}
    assert state["enacted"] == {"state": "enacted", "at": None,
                                "evidence": enacted["enactment"]}
    assert state["verified"]["state"] == "pending"
    assert state["verified"]["reported"]["at"] is None
    assert state["verified"]["reported"]["output_sha256"] == OUTPUT_SHA
    assert proposal == original  # Raw metadata and physical order are evidence.


@pytest.mark.parametrize("timestamp, date", [
    ("2026-09-05T12:00:00Z", "2026-09-05"),
    ("2026-09-05T12:00:00.123+05:30", "2026-09-05"),
    ("2040-01-02T00:15:00+05:30", "2040-01-02"),
    ("2040-01-01T23:15:00-04:00", "2040-01-01"),
    ("2026-09-05 12:00:00+00:00", "2026-09-05"),
    ("2026-09-05T12:00:00", "2026-09-05"),
    ("2024-02-29T12:00:00+23:59", "2024-02-29"),
])
def test_recorded_dates_keep_source_local_day_and_future_claims_pending(monkeypatch, timestamp, date):
    monkeypatch.setattr(ps, "_commit_changed_paths", lambda _root, _sha: {SKILL_PATH})
    enacted = {"timestamp": timestamp, "proposal_id": "P-900",
               "enactment": {"commit": SHA_A, "paths": [SKILL_PATH]}}
    claimed = {"timestamp": timestamp, "proposal_id": "P-900",
               "verification": {"commit": SHA_A, "command": "pytest -q",
                                "result": "pass", "output_sha256": OUTPUT_SHA}}
    state = ps.proposal_healing_state(_proposal(OPEN, dict(ACCEPTED, timestamp=timestamp), enacted, claimed))
    assert state["accepted"]["at"] == date
    assert state["enacted"]["at"] == date
    assert state["verified"]["reported"]["at"] == date
    assert state["verified"]["state"] == "pending"


def test_missing_time_does_not_add_verification_or_change_append_verdict(monkeypatch):
    monkeypatch.setattr(ps, "_commit_changed_paths", lambda _root, _sha: {SKILL_PATH})
    accepted = {k: v for k, v in ACCEPTED.items() if k != "timestamp"}
    enacted = {"proposal_id": "P-900", "enactment": {"commit": SHA_A, "paths": [SKILL_PATH]}}
    state = ps.proposal_healing_state(_proposal(OPEN, accepted, enacted))
    assert state["accepted"]["at"] is None
    assert state["enacted"]["state"] == "enacted" and state["enacted"]["at"] is None
    assert state["verified"] == {"state": "pending"}
    before = ps.proposal_healing_state(_proposal(OPEN, enacted, accepted))
    assert before["enacted"] == {"state": "pending"}
    rejected = dict(ACCEPTED, verdict="rejected", timestamp="not-a-time")
    after = ps.proposal_healing_state(_proposal(OPEN, accepted, enacted, rejected))
    assert after["accepted"]["state"] == "unknown"
    assert after["enacted"]["state"] == "unknown"


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

    claimed = {
        "timestamp": "2026-08-05T00:00:00Z", "proposal_id": "P-900", "status": "verified",
        "verification": {"commit": SHA_A, "command": "pytest -q", "result": "pass",
                         "output_sha256": OUTPUT_SHA},
    }
    lifecycle = ps.proposal_healing_state(_proposal(OPEN, ACCEPTED, enacted, claimed))
    assert lifecycle["verified"]["state"] == "pending"
    assert lifecycle["verified"]["reported"]["output_sha256"] == OUTPUT_SHA


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


@pytest.mark.parametrize("before_accept, expected", [(True, "pending"), (False, "enacted")])
def test_projector_uses_append_order_despite_misleading_timestamps(monkeypatch, before_accept, expected):
    monkeypatch.setattr(ps, "_commit_changed_paths", lambda _root, _sha: {SKILL_PATH})
    evidence = {
        "timestamp": "2026-08-05T00:00:00Z" if before_accept else "2026-08-01T12:00:00Z",
        "proposal_id": "P-900", "enactment": {"commit": SHA_A, "paths": [SKILL_PATH]},
    }
    rows = [OPEN, evidence, ACCEPTED] if before_accept else [OPEN, ACCEPTED, evidence]
    proposal = ps.collapse_proposals(rows)["P-900"]
    assert proposal["lifecycle"] == rows
    assert ps.proposal_healing_state(proposal)["enacted"]["state"] == expected


@pytest.mark.parametrize("before_accept, expected", [(True, "pending"), (False, "enacted")])
def test_health_loader_preserves_physical_ledger_order(tmp_path, monkeypatch, before_accept, expected):
    monkeypatch.setattr(ps, "_commit_changed_paths", lambda _root, _sha: {SKILL_PATH})
    evidence = {
        "timestamp": "2026-08-05T00:00:00Z" if before_accept else "2026-08-01T12:00:00Z",
        "proposal_id": "P-900", "enactment": {"commit": SHA_A, "paths": [SKILL_PATH]},
    }
    rows = [OPEN, evidence, ACCEPTED] if before_accept else [OPEN, ACCEPTED, evidence]
    ledger = tmp_path / "proposals.jsonl"
    ledger.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    loaded = ph.load_proposals(ledger)["P-900"]
    assert loaded == rows
    assert ph.proposal_state(loaded, tmp_path)["enacted"]["state"] == expected


def test_backdated_rejection_remains_the_governing_verdict():
    rejected = dict(ACCEPTED, timestamp="2026-08-01T12:00:00Z", verdict="rejected")
    proposal = ps.collapse_proposals([OPEN, ACCEPTED, rejected])["P-900"]
    assert ps.final_verdict(proposal) == "rejected"
    assert ps.proposal_healing_state(proposal)["accepted"]["state"] == "unknown"


def test_verification_record_before_enactment_is_not_a_later_receipt(monkeypatch):
    monkeypatch.setattr(ps, "_commit_changed_paths", lambda _root, _sha: {SKILL_PATH})
    claimed = {
        "timestamp": "2026-08-03T00:00:00Z", "proposal_id": "P-900",
        "verification": {"commit": SHA_A, "command": "pytest -q", "result": "pass",
                         "output_sha256": OUTPUT_SHA},
    }
    enacted = {
        "timestamp": "2026-08-04T00:00:00Z", "proposal_id": "P-900",
        "enactment": {"commit": SHA_A, "paths": [SKILL_PATH]},
    }
    state = ps.proposal_healing_state(_proposal(OPEN, ACCEPTED, claimed, enacted))
    assert state["verified"]["state"] == "pending"
    assert "reported" not in state["verified"]


def test_well_shaped_receipt_is_reported_without_healing(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(ps, "_commit_changed_paths", lambda _root, _sha: {SKILL_PATH})
    monkeypatch.setattr(ps, "skill_born_date", lambda _name: None)
    enacted = {
        "timestamp": "2026-08-03T00:00:00Z", "proposal_id": "P-900",
        "enactment": {"commit": SHA_A, "paths": [SKILL_PATH]},
    }
    claimed = {
        "timestamp": "2026-08-04T00:00:00Z", "proposal_id": "P-900",
        "verification": {"commit": SHA_A, "command": "pytest -q", "result": "pass",
                         "output_sha256": OUTPUT_SHA},
    }
    rows = [OPEN, ACCEPTED, enacted, claimed]
    proposal = _proposal(*rows)
    skills, _ = ps.build_skills(
        [{"name": "validate", "layer": "A", "pack": "core", "runtime_safe": "true"}],
        [], {}, {"P-900": proposal}, [], [], "2026-08-01", "2026-08-07",
    )
    assert skills[0]["governance"]["healed"] is None
    assert skills[0]["governance"]["state"] != "healed"

    ledger = tmp_path / "memory" / "brain" / "proposals.jsonl"
    ledger.parent.mkdir(parents=True)
    ledger.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    monkeypatch.setattr(ph, "find_commits", lambda _root, _pid: [])
    monkeypatch.setattr(sys, "argv", ["proposal_health.py", "--repo-root", str(tmp_path)])
    assert ph.main() == 0  # structural enactment clears this report's existing check
    output = capsys.readouterr().out
    assert "| accepted | enacted | pending |" in output
    assert "reported verification claims (not independently verified): P-900" in output


@pytest.mark.parametrize("enacted, pending", [(False, 0), (True, 1)])
def test_loop_verification_queue_counts_only_enacted_unverified_skills(monkeypatch, enacted, pending):
    monkeypatch.setattr(ps, "_commit_changed_paths", lambda _root, _sha: {SKILL_PATH})
    monkeypatch.setattr(ps, "skill_born_date", lambda _name: None)
    rows = [OPEN, ACCEPTED]
    if enacted:
        rows.extend([
            {"proposal_id": "P-900", "timestamp": "2026-08-03T00:00:00Z",
             "enactment": {"commit": SHA_A, "paths": [SKILL_PATH]}},
            {"proposal_id": "P-900", "timestamp": "2026-08-04T00:00:00Z",
             "verification": {"commit": SHA_A, "command": "pytest -q", "result": "pass",
                              "output_sha256": OUTPUT_SHA}},
        ])
    proposals = {"P-900": _proposal(*rows)}
    skills, _ = ps.build_skills(
        [{"name": "validate", "layer": "A", "pack": "core", "runtime_safe": "true"}],
        [], {}, proposals, [], [], "2026-08-01", "2026-08-07",
    )
    loop = ps.build_loop(proposals, [], [], skills, "2026-08-07")
    assert loop["stages"]["verified"] == {"skills": 0, "pending": pending}
    assert loop["stages"]["enacted"]["skills_healed"] == 0


@pytest.mark.parametrize("lane", ["rejected", "draft"])
def test_health_does_not_count_rejections_or_drafts_as_open(tmp_path, monkeypatch, capsys, lane):
    rows = ([OPEN, dict(ACCEPTED, verdict="rejected")] if lane == "rejected"
            else [dict(OPEN, status="draft")])
    path = tmp_path / "memory" / "brain" / "proposals.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    monkeypatch.setattr(sys, "argv", ["proposal_health.py", "--repo-root", str(tmp_path)])
    assert ph.main() == 0
    output = capsys.readouterr().out
    assert "median days open" not in output
    assert f"| P-900 | {lane} |" in output
    if lane == "rejected":
        assert "1.0 (days→verdict)" in output
        assert "median days→verdict (closed proposals): 1.0" in output
    else:
        assert "days draft" in output


@pytest.mark.parametrize("verdict", ["rejected", "auto-reject"])
def test_rejection_incident_and_rule_keep_governing_verdict_provenance(verdict):
    rejected = dict(ACCEPTED, verdict=verdict, rule_cited="FR-900", verdict_reasoning="recorded reason")
    annotation = {"proposal_id": "P-900", "timestamp": "2026-08-07T00:00:00Z", "note": "later annotation"}
    proposals = {"P-900": _proposal(OPEN, rejected, annotation)}
    rules = [{"rule_id": "FR-900", "title": "Fixture rule", "body": ""}]
    _, incidents = ps.build_timeline_and_incidents(
        proposals, [], [], {}, [], [], [], rules, None, "2026-08-01", "2026-08-07",
    )
    incident = next(i for i in incidents if i["id"] == "P-900")
    assert incident["date"] == "2026-08-02"
    assert incident["what_happened"] == "recorded reason"
    assert incident["rule"] == "FR-900"
    assert incident["title"] == "P-900 " + ("auto-rejected" if verdict == "auto-reject" else "rejected") + ": Tighten validate"
    assert ps.build_rules(rules, proposals)[0]["enforced_count"] == 1


def test_review_totals_include_manual_rejection_separately():
    proposals = {"P-900": _proposal(OPEN, dict(ACCEPTED, verdict="rejected"))}
    review = ps.build_loop(proposals, [], [], [], "2026-08-07")["stages"]["review"]
    assert review["rejected"] == 1
    assert review["auto_reject"] == 0


def _timeline(*rows):
    return ps.build_timeline_and_incidents(
        ps.collapse_proposals(list(rows)), [], [], {}, [], [], [], [], None,
        "2026-08-01", "2026-08-07",
    )[0]


@pytest.mark.parametrize("receipt", [
    {"enactment": {"commit": SHA_A, "paths": [SKILL_PATH]}},
    {"verification": {"commit": SHA_A, "command": "pytest -q", "result": "pass",
                      "output_sha256": OUTPUT_SHA}},
    {"enactment": None, "verification": "pass"},
])
@pytest.mark.parametrize("status", [None, "open", "draft", "verified"])
def test_timeline_receipts_are_reported_appends_not_new_filings(receipt, status):
    # A copied filing status or malformed receipt is not another filing.
    evidence = dict(receipt, timestamp="2026-08-01T12:00:00Z",
                    proposal_id="P-900", agent_id="human:unverified-label",
                    status=status)
    rows = [OPEN, ACCEPTED, evidence]
    before = json.dumps(rows, sort_keys=True)
    timeline = _timeline(*rows)
    assert [t["kind"] for t in timeline] == [
        "proposal_reviewed", "proposal_evidence_reported", "proposal_filed",
    ]
    assert timeline[1]["ts"] == evidence["timestamp"]
    assert timeline[1]["agent"] == evidence["agent_id"]
    assert timeline[1]["verdict"] is None
    assert timeline[0]["ts"] == ACCEPTED["timestamp"]
    assert timeline[0]["agent"] == ACCEPTED["agent_id"]
    proposal = ps.collapse_proposals(rows)["P-900"]
    assert proposal["lifecycle"] == rows  # Display order is not lifecycle order.
    assert ps._proposal_verdict_row(proposal) == ACCEPTED
    assert ps.final_verdict(proposal) == "accepted"
    assert json.dumps(rows, sort_keys=True) == before


@pytest.mark.parametrize("annotation", [
    {}, {"note": "verified by human; pass; " + OUTPUT_SHA},
    {"status": "closed"}, {"status": "enacted"}, {"status": "verified"},
    {"status": "future-status", "evidence": "pass"},
])
def test_timeline_unknown_annotations_never_invent_a_filing(annotation):
    row = dict(annotation, proposal_id="P-900", timestamp="2026-08-03T00:00:00Z")
    for rows in [(row,), (OPEN, ACCEPTED, row)]:
        event = _timeline(*rows)[0]
        assert event["kind"] == "proposal_annotation_unknown"
        assert event["agent"] == "unknown"
        assert event["verdict"] is None


def test_timeline_keeps_explicit_draft_promotion_and_refiling_history():
    draft = dict(OPEN, status="draft", agent_id="draft:auto")
    # Existing graduate_drafts.py promotion shape; do not execute that writer.
    promoted = {"timestamp": "2026-08-02T00:00:00Z", "proposal_id": "P-900",
                "supersedes_proposal_id": "P-900", "agent_id": "auto:graduated",
                "status": "open"}
    revised = dict(OPEN, timestamp="2026-08-03T00:00:00Z",
                   title="Revised validate change", references=["P-900"])
    timeline = _timeline(draft, promoted, revised)
    assert [t["kind"] for t in timeline] == [
        "proposal_filed", "proposal_filed", "proposal_drafted",
    ]
    assert timeline[0]["title"] == revised["title"]
    assert timeline[1]["agent"] == promoted["agent_id"]
    assert timeline[2]["title"] == draft["title"]
    assert len(timeline) == 3


def test_timeline_verdict_takes_precedence_without_authenticating_receipts(monkeypatch):
    monkeypatch.setattr(ps, "_commit_changed_paths", lambda _root, _sha: {SKILL_PATH})
    enactment = {"timestamp": "2026-08-03T00:00:00Z", "proposal_id": "P-900",
                 "enactment": {"commit": SHA_A, "paths": [SKILL_PATH]}}
    receipt = {"timestamp": "2026-08-04T00:00:00Z", "proposal_id": "P-900",
               "agent_id": "human:unverified-label",
               "verification": {"commit": SHA_A, "command": "pytest -q",
                                "result": "pass", "output_sha256": OUTPUT_SHA}}
    rows = [OPEN, ACCEPTED, enactment, receipt]
    assert _timeline(*rows)[0]["kind"] == "proposal_evidence_reported"
    state = ps.proposal_healing_state(ps.collapse_proposals(rows)["P-900"])
    assert state["verified"]["state"] == "pending"
    assert state["verified"]["reported"]["result"] == "pass"
    # Actor text and a pass-shaped receipt cannot create an acceptance.
    assert ps.proposal_healing_state(_proposal(OPEN, receipt))["accepted"]["state"] == "unknown"
    rejected = dict(ACCEPTED, timestamp="2026-08-01T12:00:00Z", verdict="rejected",
                    verification=receipt["verification"])
    rows.append(rejected)
    event = next(t for t in _timeline(*rows) if t["verdict"] == "rejected")
    assert event["kind"] == "proposal_reviewed"
    assert event["agent"] == rejected["agent_id"]
    assert event["ts"] == rejected["timestamp"]
    assert ps.final_verdict(ps.collapse_proposals(rows)["P-900"]) == "rejected"


def test_timeline_labels_render_in_existing_dashboard_consumer():
    from test_ui_data_provenance import run_js

    rows = _timeline(
        dict(OPEN, status="draft"), ACCEPTED,
        {"timestamp": "2026-08-03T00:00:00Z", "proposal_id": "P-900",
         "agent_id": "human:<reported>", "verification": "pass"},
        {"timestamp": "2026-08-04T00:00:00Z", "proposal_id": "P-900", "note": "x"},
    )
    assert all(set(row) == {"date", "ts", "kind", "id", "title", "agent",
                            "verdict", "is_flag", "skill"} for row in rows)
    run_js(r"""
const rows=ROWS;
context.BRAIN_SUMMARY={timeline:rows};
const html=fs.readFileSync(process.argv[1]+'/dashboard.html','utf8');
const script=html.match(/<script>([\s\S]*?)<\/script>/)[1];
// Run the real timeline renderer with isolated data and no page boot/fetch.
vm.runInContext(`const U=UI, D=BRAIN_SUMMARY, esc=U.esc;
const $=id=>document.getElementById(id), inWin=()=>true, windowDays=7;`+
  script.slice(script.indexOf('const KIND_COLOR'),script.indexOf('/* ---------- rules')),context);
let panel='';U.panel.open=(_,html)=>{panel=html;};
vm.runInContext('renderTimeline();openTimeline();',context);
assert.equal(elements.get('timeline').children.length,rows.length);
for(const kind of ['proposal_drafted','proposal_reviewed','proposal_evidence_reported',
                   'proposal_annotation_unknown'])assert.ok(panel.includes(kind));
assert.ok(panel.includes('human:&lt;reported&gt;'));
assert.doesNotMatch(panel,/>pass<\/span>/);
""".replace("ROWS", json.dumps(rows)))
