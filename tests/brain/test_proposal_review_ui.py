"""Static contract tests for the proposal-review actor assertion controls."""
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
