#!/usr/bin/env python3
"""Tests for scripts/draft_proposals.py — the drift-signal "bubbling" pipeline.

We exercise the two pure surfaces against TEMP ledgers, never the real files:
  - signal_candidates(skills, covered_skills) — one candidate per drift signal in
    drift_signals.jsonl on a framework skill not already covered.
  - build_drafts() — mints DRAFT rows (status "draft", agent "draft:auto") from
    admitted candidates, reports bounded rejection/suppression reasons, and is
    idempotent on a re-run.

The module pins ledger paths as module-level constants (dp.DRIFT_SIGNALS,
dp.FEEDBACK, dp.PROPOSALS) and discovers skills via dp.framework_skills(). We
monkeypatch all of these at tmp fixtures so the real brain is untouched. drafts()
re-reads dp.PROPOSALS, so the idempotency leg appends the minted rows back to the
same temp file before the second build_drafts() call.
"""
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import draft_proposals as dp  # noqa: E402


# Two valid drift signals on framework skills, mirroring the SHARED drift schema:
# one schema violation from the deterministic scan, one runtime self-report.
SIG_SCAN = {
    "timestamp": "2026-06-16T10:00:00Z", "signal_id": "DS-0001",
    "source": "scan", "detector": "runlog_schema", "skill": "run-log",
    "status_observed": "recovered", "ref": "framework.run.jsonl:L42",
    "severity": "low", "evidence": "framework status is outside FR-003",
    "scope": "framework",
}
SIG_RUNTIME = {
    "timestamp": "2026-06-16T11:00:00Z", "signal_id": "DS-0002",
    "source": "runtime", "detector": "runtime_selfreport", "skill": "validate",
    "status_observed": "gap", "ref": "skill_signals.jsonl:L2 task=D-041",
    "severity": "low", "evidence": "validate lacks an n/a disposition",
    "scope": "framework",
}

# Historical compatibility fixture only. ``runlog_failure`` was retired by
# Option 3: an honest failed/refused/escalated outcome is not current drift.
SIG_LEGACY_OUTCOME = {
    "timestamp": "2026-06-16T09:00:00Z", "signal_id": "DS-0000",
    "source": "scan", "detector": "runlog_failure", "skill": "fallback",
    "status_observed": "failed", "ref": "framework.run.jsonl:L41",
    "severity": "high", "evidence": "historical retired outcome trigger",
    "scope": "framework",
}

FRAMEWORK_SKILLS = {"fallback", "validate", "run-log", "gate-check"}


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w") as f:
        for r in rows:
            f.write(json.dumps(r, separators=(",", ":"), ensure_ascii=False) + "\n")


@pytest.fixture
def bubble_env(tmp_path, monkeypatch):
    """Point dp's ledgers at temp files and pin framework_skills().

    Captures the real ledger paths' contents are never touched: we only ever
    write the temp paths the constants now point at.
    """
    drift = tmp_path / "drift_signals.jsonl"
    feedback = tmp_path / "feedback.jsonl"
    proposals = tmp_path / "proposals.jsonl"
    _write_jsonl(drift, [SIG_SCAN, SIG_RUNTIME])
    feedback.write_text("")          # empty harvest ledger — source 1 yields nothing
    proposals.write_text("")         # no existing proposals

    monkeypatch.setattr(dp, "DRIFT_SIGNALS", drift)
    monkeypatch.setattr(dp, "FEEDBACK", feedback)
    monkeypatch.setattr(dp, "PROPOSALS", proposals)
    monkeypatch.setattr(dp, "framework_skills", lambda: set(FRAMEWORK_SKILLS))
    return tmp_path, drift, feedback, proposals


def test_signal_candidates_one_per_uncovered_signal(bubble_env):
    cands = dp.signal_candidates(FRAMEWORK_SKILLS, covered_skills=set())
    assert len(cands) == 2
    targets = {c["target"] for c in cands}
    assert targets == {"run-log", "validate"}
    # source_ref is the signal's own ref (the idempotency key half).
    refs = {c["source_ref"] for c in cands}
    assert "framework.run.jsonl:L42" in refs
    assert "skill_signals.jsonl:L2 task=D-041" in refs


@pytest.mark.parametrize("omitted", [True, False])
def test_missing_ref_reports_source_line_without_minting(bubble_env, omitted):
    _tmp, drift, _feedback, proposals = bubble_env
    signal = {**SIG_RUNTIME, "ref": None}
    if omitted:
        del signal["ref"]
    _write_jsonl(drift, [signal])
    before = proposals.read_bytes()
    new, skipped = dp.build_drafts()
    assert new == []
    assert skipped == [{"target": "validate", "source_ref": "drift_signals.jsonl:L1",
                        "reason": "missing source ref"}]
    assert proposals.read_bytes() == before


def test_signal_candidates_skips_covered_skills(bubble_env):
    # `run-log` is already spoken to by a non-draft proposal → skip it.
    cands = dp.signal_candidates(FRAMEWORK_SKILLS, covered_skills={"run-log"})
    assert {c["target"] for c in cands} == {"validate"}


def test_signal_candidates_skips_non_framework_skill(bubble_env, tmp_path):
    # A signal whose skill is NOT a framework skill must not bubble.
    drift = tmp_path / "drift_signals.jsonl"
    _write_jsonl(drift, [SIG_SCAN, {**SIG_RUNTIME, "skill": "not-a-real-skill"}])
    cands = dp.signal_candidates(FRAMEWORK_SKILLS, covered_skills=set())
    assert {c["target"] for c in cands} == {"run-log"}


def test_build_drafts_mints_draft_rows(bubble_env):
    new_drafts, skipped = dp.build_drafts()
    assert len(new_drafts) == 2
    assert skipped == []
    for d in new_drafts:
        assert d["status"] == dp.DRAFT_STATUS == "draft"
        assert d["agent_id"] == dp.DRAFT_AGENT == "draft:auto"
        assert d["target_type"] == "skill"
        assert d["scope"] == "framework"
        assert d["proposal_id"].startswith("P-")
        # references carry the source_ref then the skill (the dedup key half).
        assert d["target"] in d["references"]
    assert {d["target"] for d in new_drafts} == {"run-log", "validate"}
    # Sequential, distinct ids.
    ids = [d["proposal_id"] for d in new_drafts]
    assert len(set(ids)) == len(ids)


def test_build_drafts_idempotent_after_append(bubble_env):
    _tmp, _drift, _feedback, proposals = bubble_env
    first, _ = dp.build_drafts()
    assert len(first) == 2
    # Simulate --apply: append the minted drafts back into the temp ledger.
    dp.append_drafts(first)
    # Second pass sees them as already-drafted (dedup on (target, source_ref)).
    second, skipped = dp.build_drafts()
    assert second == []
    assert len(skipped) == 2
    assert all(s["reason"] == "already drafted" for s in skipped)
    # drafts() reflects exactly the two appended rows.
    assert {d["target"] for d in dp.drafts()} == {"run-log", "validate"}


def test_build_drafts_skips_already_covered_skill(bubble_env):
    _tmp, _drift, _feedback, proposals = bubble_env
    # Seed an OPEN (non-draft) proposal that already targets `run-log`.
    open_prop = {
        "timestamp": "2026-06-01T00:00:00Z", "proposal_id": "P-050",
        "agent_id": "claude-code-main", "title": "Tighten fallback",
        "target_type": "skill", "target": "run-log",
        "change": "x", "reasoning": "y", "status": "open",
    }
    _write_jsonl(proposals, [open_prop])
    new_drafts, _ = dp.build_drafts()
    # Only `validate` bubbles; `run-log` is covered.
    assert {d["target"] for d in new_drafts} == {"validate"}
    # And next id continues past the existing P-050.
    assert new_drafts[0]["proposal_id"] == "P-051"


# ---------------------------------------------------------------------------
# AS023 admission + inspectable rejection/suppression diagnostics
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("outcome", ["failed", "refused", "escalated"])
def test_retired_outcome_trigger_is_inert_and_reported(bubble_env, outcome):
    _tmp, drift, _feedback, _proposals = bubble_env
    row = {**SIG_LEGACY_OUTCOME, "status_observed": outcome}
    _write_jsonl(drift, [row])

    new_drafts, skipped = dp.build_drafts()

    assert new_drafts == []
    assert skipped == [{
        "target": "fallback",
        "source_ref": "framework.run.jsonl:L41",
        "reason": "invalid signal trigger",
    }]


@pytest.mark.parametrize("status", ["friction", "diverged", "gap"])
def test_runtime_output_vocabulary_remains_admitted(bubble_env, status):
    _tmp, drift, _feedback, _proposals = bubble_env
    _write_jsonl(drift, [{**SIG_RUNTIME, "status_observed": status}])

    new_drafts, skipped = dp.build_drafts()

    assert len(new_drafts) == 1
    assert new_drafts[0]["target"] == "validate"
    assert f"runtime_selfreport, {status}" in new_drafts[0]["change"]
    assert skipped == []


@pytest.mark.parametrize(
    ("updates", "target", "source_ref", "reason"),
    [
        ({"status_observed": "misuse"}, "validate",
         "skill_signals.jsonl:L2 task=D-041",
         "invalid runtime output class: producer misuse must map to diverged"),
        ({"status_observed": "typo-class"}, "validate",
         "skill_signals.jsonl:L2 task=D-041", "invalid runtime output class"),
        ({"status_observed": ""}, "validate",
         "skill_signals.jsonl:L2 task=D-041", "missing runtime output class"),
        ({"status_observed": []}, "validate",
         "skill_signals.jsonl:L2 task=D-041", "invalid status_observed type"),
        ({"status_observed": {}}, "validate",
         "skill_signals.jsonl:L2 task=D-041", "invalid status_observed type"),
        ({"source": []}, "validate", "skill_signals.jsonl:L2 task=D-041",
         "invalid source type"),
        ({"detector": {}}, "validate", "skill_signals.jsonl:L2 task=D-041",
         "invalid detector type"),
        ({"source": "scan"}, "validate", "skill_signals.jsonl:L2 task=D-041",
         "invalid signal trigger"),
        ({"skill": ""}, "<missing>", "skill_signals.jsonl:L2 task=D-041",
         "missing skill"),
        ({"skill": []}, "<invalid>", "skill_signals.jsonl:L2 task=D-041",
         "invalid skill type"),
        ({"skill": {}}, "<invalid>", "skill_signals.jsonl:L2 task=D-041",
         "invalid skill type"),
        ({"skill": "unknown-skill"}, "unknown-skill",
         "skill_signals.jsonl:L2 task=D-041", "unknown framework skill"),
        ({"ref": ""}, "validate", "drift_signals.jsonl:L1",
         "missing source ref"),
        ({"ref": []}, "validate", "drift_signals.jsonl:L1",
         "invalid source ref type"),
        ({"ref": {}}, "validate", "drift_signals.jsonl:L1",
         "invalid source ref type"),
    ],
)
def test_malformed_drift_inputs_are_inert_inspectable_and_non_crashing(
        bubble_env, updates, target, source_ref, reason):
    _tmp, drift, _feedback, _proposals = bubble_env
    _write_jsonl(drift, [{**SIG_RUNTIME, **updates}])

    new_drafts, skipped = dp.build_drafts()

    assert new_drafts == []
    assert skipped == [{
        "target": target,
        "source_ref": source_ref,
        "reason": reason,
    }]


def test_exact_duplicate_input_is_reported_once(bubble_env):
    _tmp, drift, _feedback, _proposals = bubble_env
    _write_jsonl(drift, [SIG_RUNTIME, {**SIG_RUNTIME, "signal_id": "DS-0999"}])

    new_drafts, skipped = dp.build_drafts()

    assert len(new_drafts) == 1
    assert skipped == [{
        "target": "validate",
        "source_ref": "skill_signals.jsonl:L2 task=D-041",
        "reason": "duplicate input signal",
    }]


@pytest.mark.parametrize(
    ("filing_status", "terminal"),
    [("open", None), ("closed", None), ("open", "accepted"),
     ("open", "rejected")],
)
def test_broad_covered_skill_policy_is_retained_and_reported(
        bubble_env, filing_status, terminal):
    _tmp, drift, _feedback, proposals = bubble_env
    _write_jsonl(drift, [SIG_RUNTIME])
    filing = {
        "timestamp": "2026-06-01T00:00:00Z", "proposal_id": "P-050",
        "agent_id": "test", "title": "Existing validate proposal",
        "target_type": "skill", "target": "validate",
        "change": "x", "reasoning": "y", "status": filing_status,
    }
    rows = [filing]
    if terminal is not None:
        rows.append({
            "timestamp": "2026-06-02T00:00:00Z", "proposal_id": "P-050",
            "verdict": terminal, "status": "closed",
        })
    _write_jsonl(proposals, rows)

    new_drafts, skipped = dp.build_drafts()

    assert new_drafts == []
    assert skipped == [{
        "target": "validate",
        "source_ref": "skill_signals.jsonl:L2 task=D-041",
        "reason": "covered by existing non-draft proposal",
    }]


def test_harvest_coverage_and_duplicate_are_reported(bubble_env):
    _tmp, drift, feedback, proposals = bubble_env
    _write_jsonl(drift, [])
    finding = {
        "harvest_id": "H099", "class": "friction", "skill": "validate",
        "ref": "private.run.jsonl:L9", "evidence": "valid harvest friction",
        "plan_candidate": "tighten validation",
    }
    _write_jsonl(feedback, [finding, finding])
    _write_jsonl(proposals, [])
    drafts, skipped = dp.build_drafts()
    assert len(drafts) == 1
    assert skipped == [{
        "target": "validate",
        "source_ref": "feedback.jsonl:H099:private.run.jsonl:L9",
        "reason": "duplicate harvest finding",
    }]

    _write_jsonl(proposals, [{
        "timestamp": "2026-06-01T00:00:00Z", "proposal_id": "P-050",
        "agent_id": "test", "title": "Existing validate proposal",
        "target_type": "skill", "target": "validate",
        "change": "x", "reasoning": "y", "status": "closed",
    }])
    drafts, skipped = dp.build_drafts()
    assert drafts == []
    assert skipped == [{
        "target": "validate",
        "source_ref": "feedback.jsonl:H099:private.run.jsonl:L9",
        "reason": "covered by existing non-draft proposal",
    }, {
        "target": "validate",
        "source_ref": "feedback.jsonl:H099:private.run.jsonl:L9",
        "reason": "covered by existing non-draft proposal",
    }]


def test_cli_prints_all_rejection_and_suppression_reasons(
        bubble_env, monkeypatch, capsys):
    _tmp, drift, _feedback, _proposals = bubble_env
    _write_jsonl(drift, [SIG_LEGACY_OUTCOME, {**SIG_RUNTIME, "skill": "no-skill"}])
    monkeypatch.setattr(sys, "argv", ["draft_proposals.py", "--dry-run"])

    assert dp.main() == 0
    stdout = capsys.readouterr().out

    assert "invalid signal trigger" in stdout
    assert "unknown framework skill" in stdout
    assert "framework.run.jsonl:L41" in stdout
    assert "skill_signals.jsonl:L2 task=D-041" in stdout


# ---------------------------------------------------------------------------
# resolved-finding guard (source 1) — a finding whose remedy already shipped
# (proposes a 'new skill' that now exists) is reported as resolved, not bubbled
# ---------------------------------------------------------------------------

def test_harvest_skips_finding_whose_remedy_shipped(bubble_env):
    _tmp, drift, feedback, _proposals = bubble_env
    _write_jsonl(drift, [])  # silence the drift source; isolate source 1
    _write_jsonl(feedback, [
        # proposes creating gate-check, which EXISTS -> resolved, not bubbled
        {"harvest_id": "H002", "class": "gap", "skill": "run-log",
         "ref": "x:L1", "evidence": "needs a verdict capture",
         "plan_candidate": "new skill 'gate-check' to halt at gates"},
        # proposes creating a skill that does NOT exist -> bubbles
        {"harvest_id": "H003", "class": "gap", "skill": "fallback",
         "ref": "y:L2", "evidence": "no parallel-track protocol",
         "plan_candidate": "new skill `parallel-worktree` for tracks"},
    ])
    cands, resolved = dp.harvest_signals(FRAMEWORK_SKILLS, covered_skills=set())

    assert {c["target"] for c in cands} == {"fallback"}
    assert len(resolved) == 1
    assert resolved[0]["target"] == "run-log"
    assert "gate-check" in resolved[0]["reason"]


def test_resolved_finding_named_only_when_actually_proposing_new_skill(bubble_env):
    """The guard must NOT fire on a finding that merely MENTIONS an existing skill
    without proposing to create it (no 'new skill' phrasing)."""
    _tmp, drift, feedback, _proposals = bubble_env
    _write_jsonl(drift, [])
    _write_jsonl(feedback, [
        {"harvest_id": "H004", "class": "friction", "skill": "fallback",
         "ref": "z:L3", "evidence": "fallback should run gate-check before switching",
         "plan_candidate": "note that a fallback may itself be a gated action"},
    ])
    cands, resolved = dp.harvest_signals(FRAMEWORK_SKILLS, covered_skills=set())
    # Mentions gate-check but does not propose a NEW skill -> bubbles, not resolved.
    assert {c["target"] for c in cands} == {"fallback"}
    assert resolved == []


def test_build_drafts_reports_resolved_in_skipped(bubble_env):
    _tmp, drift, feedback, _proposals = bubble_env
    _write_jsonl(drift, [])
    _write_jsonl(feedback, [
        {"harvest_id": "H002", "class": "gap", "skill": "run-log",
         "ref": "x:L1", "evidence": "e",
         "plan_candidate": "new skill 'gate-check'"},
    ])
    new_drafts, skipped = dp.build_drafts()
    assert new_drafts == []
    assert len(skipped) == 1
    assert skipped[0]["reason"].startswith("resolved")
    assert skipped[0]["target"] == "run-log"


def test_harvest_skips_finding_superseded_by_later_confirmation(bubble_env):
    """A friction finding on a skill that a LATER harvest confirmed clean is
    superseded (not bubbled); a finding NEWER than the last confirmation bubbles."""
    _tmp, drift, feedback, _proposals = bubble_env
    _write_jsonl(drift, [])
    _write_jsonl(feedback, [
        # old friction on gate-check (H001) ...
        {"harvest_id": "H001", "class": "friction", "skill": "gate-check",
         "ref": "a:L1", "evidence": "early friction", "plan_candidate": "tighten"},
        # ... later confirmed clean (H005) -> the H001 friction is superseded.
        {"harvest_id": "H005", "class": "confirmed", "skill": "gate-check",
         "ref": "b:L2", "evidence": "gate-check held"},
        # validate confirmed at H003 ...
        {"harvest_id": "H003", "class": "confirmed", "skill": "validate",
         "ref": "c:L3", "evidence": "validate held"},
        # ... but a NEWER friction at H008 must still bubble.
        {"harvest_id": "H008", "class": "friction", "skill": "validate",
         "ref": "d:L4", "evidence": "new validate friction", "plan_candidate": "x"},
    ])
    cands, resolved = dp.harvest_signals(FRAMEWORK_SKILLS, covered_skills=set())
    assert {c["target"] for c in cands} == {"validate"}     # newer finding bubbles
    assert len(resolved) == 1
    assert resolved[0]["target"] == "gate-check"
    assert "superseded" in resolved[0]["reason"]


def test_supersession_requires_a_clean_harvest_not_just_a_confirmation(bubble_env):
    """Regression (audit MAJOR-1): a harvest that BOTH confirms and re-opens a
    skill is NOT clean — the skill's still-open findings must keep bubbling. The
    guard must not treat 'a confirmation exists at H_n' as 'clean at H_n'."""
    _tmp, drift, feedback, _proposals = bubble_env
    _write_jsonl(drift, [])
    _write_jsonl(feedback, [
        # fallback: open at H002, and at H008 BOTH confirmed AND re-opened.
        {"harvest_id": "H002", "class": "friction", "skill": "fallback",
         "ref": "a:L1", "evidence": "old fallback friction", "plan_candidate": "x"},
        {"harvest_id": "H008", "class": "confirmed", "skill": "fallback",
         "ref": "b:L2", "evidence": "fallback held in one case"},
        {"harvest_id": "H008", "class": "gap", "skill": "fallback",
         "ref": "c:L3", "evidence": "fallback still lacks batch carryover",
         "plan_candidate": "y"},
    ])
    cands, resolved = dp.harvest_signals(FRAMEWORK_SKILLS, covered_skills=set())
    # H008 re-opened fallback, so it is NOT a clean watermark -> nothing superseded.
    assert {c["target"] for c in cands} == {"fallback"}
    assert len(cands) == 2
    assert resolved == []


def test_resolved_guard_takes_first_named_token_after_new_skill(bubble_env):
    """A finding proposing a genuinely-new skill that merely quotes an existing
    skill name elsewhere must still bubble — the guard takes the FIRST named token
    after 'new skill' (the one being proposed), not any existing-skill mention."""
    _tmp, drift, feedback, _proposals = bubble_env
    _write_jsonl(drift, [])
    _write_jsonl(feedback, [
        {"harvest_id": "H008", "class": "gap", "skill": "fallback",
         "ref": "p:L1", "evidence": "needs a parallel-track protocol",
         "plan_candidate": "new skill `parallel-worktree` (cf. `validate` discipline)"},
    ])
    cands, resolved = dp.harvest_signals(FRAMEWORK_SKILLS, covered_skills=set())
    assert {c["target"] for c in cands} == {"fallback"}   # parallel-worktree is new
    assert resolved == []
