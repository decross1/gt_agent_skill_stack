#!/usr/bin/env python3
"""Tests for scripts/brain_server.py — the dynamic proposal-review backend.

These exercise the module's PURE functions (no HTTP server, no real LLM):
  - open_framework_proposals  — scope filter excludes research/a_bgt_rsi targets
  - generate_card             — persists ONE card; a re-GET reads it back with no
                                second gemma call (the file is canonical)
  - discuss_turn              — appends user + assistant turns to the cards ledger
  - write_handoff             — writes handoffs/<id>.md

Design invariant under test: Gemma is only a drafting assistant; every output is
written through to the append-only ledger, and projection/re-reads never call the
model. We assert this by counting calls on a deterministic gemma STUB.

The module pins its paths at import time as module-level constants
(brain_server.PROPOSALS, .CARDS, .FEEDBACK, .RULES, .SKILLS, .HANDOFFS, .ROOT).
We monkeypatch all of them at a tmp fixture dir so the real brain is untouched.
write_handoff returns `path.relative_to(ROOT)`, so ROOT is repointed at tmp too.
"""
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

import brain_server as bs  # noqa: E402


# A framework proposal (target is a skill) and a research one (target names the
# a_bgt_rsi consumer apparatus) — proposal_scope() should exclude the latter.
FW_PROP = {
    "timestamp": "2026-06-01T00:00:00Z", "proposal_id": "P-100",
    "agent_id": "claude-code-main", "title": "Tighten the validate skill",
    "target_type": "skill", "target": "validate",
    "change": "make near-misses always fail", "reasoning": "no coercion",
    "status": "open",
}
RESEARCH_PROP = {
    "timestamp": "2026-06-01T00:01:00Z", "proposal_id": "P-200",
    "agent_id": "nara", "title": "Refactor the apparatus loop",
    "target_type": "file", "target": "a_bgt_rsi/orchestrator/loop.py",
    "change": "split the loop", "reasoning": "too long",
    "status": "open",
}
RESEARCH_PROP_EXPLICIT = {
    "timestamp": "2026-06-01T00:02:00Z", "proposal_id": "P-300",
    "agent_id": "nara", "title": "Explicitly research-scoped",
    "target_type": "skill", "target": "validate", "scope": "research",
    "change": "x", "reasoning": "y", "status": "open",
}


class GemmaStub:
    """Deterministic stand-in for brain_server.gemma. Records call count and the
    last messages so tests can assert no-LLM-on-reread and turn ordering."""

    def __init__(self, reply=None):
        self.calls = 0
        self.last_messages = None
        # Default reply is strict card JSON so generate_card's json.loads path
        # (not its parse-fallback) is what we exercise.
        self._reply = reply or json.dumps({
            "means": "It makes validate fail on near-misses.",
            "pros_accept": ["honest checks"], "cons_accept": ["more red runs"],
            "pros_reject": ["less churn"], "cons_reject": ["hides drift"],
            "rule_check": {"conflict": False, "rule": None, "why": "consistent"},
        })

    def __call__(self, messages, max_tokens=700, temperature=0.3):
        self.calls += 1
        self.last_messages = messages
        return self._reply


@pytest.fixture
def brain(tmp_path, monkeypatch):
    """A self-contained tmp brain: monkeypatch every path constant + gemma.

    Yields a namespace with the fixture dir, the gemma stub, and a seed() helper
    that writes proposals into the temp ledger.
    """
    root = tmp_path
    brain_dir = root / "memory" / "brain"
    brain_dir.mkdir(parents=True)
    skills = root / ".agents" / "skills"
    skills.mkdir(parents=True)
    (skills / "validate").mkdir()
    (skills / "validate" / "SKILL.md").write_text(
        "---\nlayer: A\n---\n# validate\nRun checks as independent pass/fail.\n")
    handoffs = root / "handoffs"

    proposals = brain_dir / "proposals.jsonl"
    cards = brain_dir / "proposal_cards.jsonl"
    feedback = root / "memory" / "feedback.jsonl"
    rules = brain_dir / "rules.md"
    proposals.write_text("")
    cards.write_text("")
    feedback.write_text("")
    rules.write_text("# Active rules\n\n- FR-001 never coerce a near-miss.\n")

    stub = GemmaStub()
    # Repoint ROOT so write_handoff's relative_to(ROOT) resolves inside tmp.
    monkeypatch.setattr(bs, "ROOT", root)
    monkeypatch.setattr(bs, "PROPOSALS", proposals)
    monkeypatch.setattr(bs, "CARDS", cards)
    monkeypatch.setattr(bs, "FEEDBACK", feedback)
    monkeypatch.setattr(bs, "RULES", rules)
    monkeypatch.setattr(bs, "SKILLS", skills)
    monkeypatch.setattr(bs, "HANDOFFS", handoffs)
    monkeypatch.setattr(bs, "gemma", stub)

    class Brain:
        def __init__(self):
            self.root = root
            self.proposals = proposals
            self.cards = cards
            self.handoffs = handoffs
            self.gemma = stub

        def seed(self, *rows):
            proposals.write_text("".join(json.dumps(r) + "\n" for r in rows))

        def card_lines(self):
            return [json.loads(l) for l in cards.read_text().splitlines()
                    if l.strip()]

    return Brain()


# ---------------------------------------------------------------------------
# open_framework_proposals — scope filter
# ---------------------------------------------------------------------------

def test_open_framework_proposals_excludes_research_targets(brain):
    brain.seed(FW_PROP, RESEARCH_PROP, RESEARCH_PROP_EXPLICIT)
    out = bs.open_framework_proposals()
    ids = [p["proposal_id"] for p in out]
    assert ids == ["P-100"]  # research (path-named) and explicit-scope excluded
    row = out[0]
    assert row["title"] == "Tighten the validate skill"
    assert row["target"] == "validate"
    assert row["target_type"] == "skill"
    assert row["verdict"] == "open"


def test_open_framework_proposals_excludes_decided(brain):
    """A proposal whose latest verdict is closed (accepted/rejected) drops out;
    open and human-review stay."""
    decided = dict(FW_PROP, proposal_id="P-100")
    verdict = {"timestamp": "2026-06-02T00:00:00Z", "proposal_id": "P-100",
               "agent_id": "human:ui", "verdict": "accepted", "status": "closed"}
    human_review = dict(FW_PROP, proposal_id="P-101", title="Still open for review")
    hr_verdict = {"timestamp": "2026-06-02T00:00:00Z", "proposal_id": "P-101",
                  "agent_id": "human:ui", "verdict": "human-review",
                  "status": "human-review"}
    brain.seed(decided, verdict, human_review, hr_verdict)
    ids = [p["proposal_id"] for p in bs.open_framework_proposals()]
    assert ids == ["P-101"]


# ---------------------------------------------------------------------------
# generate_card — persists one card; reread does not call gemma again
# ---------------------------------------------------------------------------

def test_generate_card_persists_one_card_and_parses_json(brain):
    brain.seed(FW_PROP)
    first = bs.proposal_first("P-100")
    card = bs.generate_card(first)

    assert brain.gemma.calls == 1
    assert card["kind"] == "card"
    assert card["proposal_id"] == "P-100"
    assert card["means"] == "It makes validate fail on near-misses."
    assert card["pros_accept"] == ["honest checks"]
    assert card["rule_check"] == {"conflict": False, "rule": None,
                                  "why": "consistent"}

    lines = brain.card_lines()
    assert len(lines) == 1  # exactly one card persisted
    assert lines[0]["proposal_id"] == "P-100"
    assert lines[0]["kind"] == "card"


def test_stored_card_reads_without_a_second_gemma_call(brain):
    """The file is canonical: once a card exists, stored_card() serves it and the
    model is NOT consulted again (the simulated re-GET path)."""
    brain.seed(FW_PROP)
    first = bs.proposal_first("P-100")
    bs.generate_card(first)
    assert brain.gemma.calls == 1

    # Simulate the do_GET branch: `stored_card(pid) or generate_card(first)`.
    cached = bs.stored_card("P-100") or bs.generate_card(first)
    assert cached["means"] == "It makes validate fail on near-misses."
    assert brain.gemma.calls == 1  # no second call
    assert len(brain.card_lines()) == 1  # no duplicate card appended


def test_generate_card_parse_fallback_on_bad_json(brain):
    """Non-JSON model output falls back to a means-only card (still persisted),
    without raising."""
    brain.gemma._reply = "this is not json at all"
    brain.seed(FW_PROP)
    first = bs.proposal_first("P-100")
    card = bs.generate_card(first)
    assert card["means"].startswith("this is not json")
    assert card["rule_check"]["why"] == "parse-fallback"
    assert len(brain.card_lines()) == 1


# ---------------------------------------------------------------------------
# discuss_turn — appends user + assistant
# ---------------------------------------------------------------------------

def test_discuss_turn_appends_user_then_assistant(brain):
    brain.gemma._reply = "Here is a sharper amended change."
    brain.seed(FW_PROP)
    first = bs.proposal_first("P-100")

    reply = bs.discuss_turn(first, "None of these options look clean.")
    assert reply == "Here is a sharper amended change."
    assert brain.gemma.calls == 1

    disc = bs.discussion("P-100")
    assert [t["role"] for t in disc] == ["user", "assistant"]
    assert disc[0]["content"] == "None of these options look clean."
    assert disc[1]["content"] == "Here is a sharper amended change."
    assert all(t["ts"] for t in disc)

    # the cards ledger now holds exactly the two discuss rows
    kinds = [r["kind"] for r in brain.card_lines()]
    assert kinds == ["discuss", "discuss"]


def test_discuss_turn_carries_prior_history_into_prompt(brain):
    brain.seed(FW_PROP)
    first = bs.proposal_first("P-100")
    bs.discuss_turn(first, "first message")
    bs.discuss_turn(first, "second message")

    # Four rows: u/a/u/a — prior turns persisted between calls.
    assert len(bs.discussion("P-100")) == 4
    # The 2nd call's prompt includes the prior user+assistant turns plus the new
    # user message (system + seed-user + 2 history + 1 new = 5 messages).
    msgs = brain.gemma.last_messages
    assert msgs[0]["role"] == "system"
    assert msgs[-1]["content"] == "second message"
    assert any(m["content"] == "first message" for m in msgs)


# ---------------------------------------------------------------------------
# write_handoff — writes handoffs/<id>.md
# ---------------------------------------------------------------------------

def test_write_handoff_writes_markdown_file(brain):
    brain.seed(FW_PROP)
    first = bs.proposal_first("P-100")
    bs.discuss_turn(first, "Let us narrow scope.")

    rel = bs.write_handoff(first)
    assert rel == "handoffs/P-100.md"
    md_path = brain.handoffs / "P-100.md"
    assert md_path.exists()

    text = md_path.read_text()
    assert "# Implementation handoff — P-100" in text
    assert "Tighten the validate skill" in text          # title
    assert "make near-misses always fail" in text        # original change
    assert "Let us narrow scope." in text                # discussion echoed
    assert "## Agreed change & implementation brief" in text


def test_write_handoff_reuses_existing_card(brain):
    """If a card already exists, write_handoff must not regenerate it (it reuses
    stored_card); only the synthesis brief calls gemma."""
    brain.seed(FW_PROP)
    first = bs.proposal_first("P-100")
    bs.generate_card(first)
    calls_after_card = brain.gemma.calls  # == 1

    bs.write_handoff(first)
    # exactly one more gemma call (the synthesis), not two (card + synth)
    assert brain.gemma.calls == calls_after_card + 1
    assert len(brain.card_lines()) == 1  # no second card row
