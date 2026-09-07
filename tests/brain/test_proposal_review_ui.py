"""Static semantic contracts for the proposal-review surface."""
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
UI = REPO / "memory" / "brain" / "view" / "proposal_review.html"


def test_verdict_modal_requires_closed_actor_selection_and_confirmation():
    text = UI.read_text()
    assert '<select id="actor-id">' in text
    assert '<option value="derrick">Derrick — human</option>' in text
    assert '<option value="oracle">Oracle — agent</option>' in text
    assert 'id="actor-confirm"' in text
    assert "not cryptographically authenticated" in text
    assert "actor_id: actorId" in text
    assert 'actorId !== "derrick" && actorId !== "oracle"' in text


def test_review_exposes_truthful_catalog_and_non_authoritative_notes():
    text = UI.read_text()
    assert 'id="proposal-search"' in text
    assert 'aria-label="Search review records"' in text
    assert "ready for review" in text
    assert "held candidates" in text
    assert "decision history" in text
    assert "candidate graduation is closed" in text
    assert "Stored model notes" in text
    assert "non-authoritative" in text
    assert "Opening a record never generates model notes" in text
    assert "first open may generate a card" not in text


def test_review_uses_semantic_record_buttons_and_dialog():
    text = UI.read_text()
    assert "<button" in text and 'class="pitem' in text
    assert 'role="dialog"' in text
    assert 'aria-modal="true"' in text
    assert 'aria-labelledby="verdict-title"' in text
    assert 'role="status"' in text
