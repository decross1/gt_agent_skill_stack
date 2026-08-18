"""Static contract for the read-only operations band in the brain dashboard."""
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
HTML = (REPO / "memory" / "brain" / "view" / "dashboard.html").read_text()


def test_operations_band_is_read_only_and_has_offline_degradation():
    assert 'id="operations"' in HTML
    assert "fetchLiveOperations" in HTML
    assert 'fetchLive("api/operations"' in HTML
    assert "read_only === true" in HTML
    assert "operations data unavailable offline" in HTML
    # It presents facts but intentionally never offers service action endpoints.
    assert "api/operations" in HTML
    assert "operations/start" not in HTML
    assert "operations/stop" not in HTML
    assert "operations/restart" not in HTML


def test_operations_band_has_narrow_layout_and_provenance_copy():
    assert "@media (max-width:780px)" in HTML
    assert "provenance/status envelope" in HTML
    assert "acceptance alone never counts as enactment" in HTML
    assert "!O.repo" in HTML
    assert "tracked_dirty_count" in HTML
    assert "untracked files, paths, and contents are intentionally excluded" in HTML
