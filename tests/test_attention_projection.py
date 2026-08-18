"""Deterministic contracts for the dashboard's authority-separated attention view."""
from datetime import datetime, timezone
from pathlib import Path
import sys


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import project_summary as ps  # noqa: E402


def _draft(pid="P-800"):
    first = {
        "timestamp": "2026-08-01T00:00:00Z", "proposal_id": pid,
        "status": "draft", "target_type": "brain-page", "target": "daily-view",
        "title": "Show an honest backlog", "change": "x", "reasoning": "y",
        "references": ["feedback.jsonl:H100:week1.run.jsonl L42"],
    }
    return {"first": first, "latest": first, "lifecycle": [first]}


def test_draft_candidate_surfaces_evidence_radius_hold_and_human_only_route():
    items = ps.build_inbox(None, [], {"P-800": _draft()}, [], [],
                           datetime(2026, 8, 18, tzinfo=timezone.utc), "2026-08-18")
    candidate = items[0]
    assert candidate["kind"] == "candidate_review"
    assert candidate["candidate"] == {
        "blast_radius": "low",
        "evidence_reference": "feedback.jsonl:H100:week1.run.jsonl L42",
        "references": ["feedback.jsonl:H100:week1.run.jsonl L42"],
        "hold_reason": "automatic graduation is closed; no attributable automated verdict writer is authorized",
        "authorized_next_route": (
            "attributable steward review only — Derrick or Oracle may triage, then "
            "route a deliberate promotion/review through the governed proposal path"
        ),
    }
    assert candidate["age_days"] == 17


def test_attention_preserves_total_and_keeps_external_authority_outside_framework():
    draft = {"id": "P-800", "kind": "candidate_review", "surface": "framework",
             "actionable": True, "title": "candidate"}
    framework = {"id": "P-801", "kind": "proposal_review", "surface": "framework",
                 "actionable": True, "title": "framework action"}
    external = {"id": "iter-1", "kind": "gate_verdict", "surface": "apparatus",
                "actionable": True, "action_cmd": "external write", "title": "external gate"}
    second_external = {"id": "iter-2", "kind": "gate_verdict", "surface": "apparatus",
                       "actionable": True, "action_cmd": "external write 2", "title": "second external gate",
                       "age_days": 3}
    finding = {"id": "finding-1", "kind": "finding_review", "surface": "apparatus",
               "actionable": True, "action_cmd": "external finding", "title": "external finding"}
    attention = ps.build_attention([draft, framework, external, second_external, finding])

    assert attention["totals"] == {"all": 5, "framework_actions": 1,
                                    "external_acknowledgements": 3, "backlog_history": 1}
    assert attention["framework_actions"] == [framework]
    assert attention["backlog_history"] == [draft]
    projected_external = attention["external_acknowledgements"][0]
    assert projected_external["id"] == "iter-1"
    assert projected_external["actionable"] is False
    assert projected_external["action_cmd"] is None
    assert "a_bgt_rsi" in projected_external["authorized_route"]
    assert "no authority" in attention["authority_note"]
    # Compact groups do not discard the three detailed view-only external rows.
    assert attention["external_groups"] == [
        {"kind": "finding_review", "count": 1,
         "representative": {"id": "finding-1", "title": "external finding", "age_days": None,
                            "since": None, "source": None}},
        {"kind": "gate_verdict", "count": 2,
         "representative": {"id": "iter-1", "title": "external gate", "age_days": None,
                            "since": None, "source": None}},
    ]


def test_attention_dashboard_static_contract_keeps_three_lanes_and_mobile_safe_layout():
    html = (REPO / "memory" / "brain" / "view" / "dashboard.html").read_text()
    assert "framework actions" in html
    assert "external a_bgt_rsi acknowledgements/history" in html
    assert "backlog / history" in html
    assert "automatic graduation is closed" in html
    assert "evidence:" in html and "blast radius:" in html and "next route:" in html
    assert "attention-group" in html
    assert "external_groups" in html
    assert "openInboxKind(group.kind)" in html
    assert "open all " in html and "view-only here" in html
    assert "header .stepper,header .asof,header .xnav{display:none}" in html
    assert "#status{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));height:auto}" in html
    assert ".rmono{display:none}" in html
