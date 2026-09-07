"""Static navigation and local asset integration, without a server or network."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, unquote

import pytest

VIEW = Path(__file__).resolve().parents[1] / "memory" / "brain" / "view"


class Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


@pytest.mark.parametrize("page", ["dashboard.html", "graph.html"])
def test_existing_views_link_to_activity(page):
    parsed = Tags()
    parsed.feed((VIEW / page).read_text())
    assert any(tag == "a" and attrs.get("href") == "activity.html" for tag, attrs in parsed.tags)


def test_activity_assets_and_primary_navigation_are_local_and_present():
    parsed = Tags()
    parsed.feed((VIEW / "activity.html").read_text())
    for tag, attrs in parsed.tags:
        path = attrs.get("src") if tag == "script" else attrs.get("href") if tag in {"link", "a"} else None
        if not path or path.startswith("#"):
            continue
        parsed_url = urlsplit(path)
        assert not parsed_url.scheme and not parsed_url.netloc and not parsed_url.path.startswith("/")
        local_path = unquote(parsed_url.path)
        assert ".." not in Path(local_path).parts
        # Query/fragment version tags do not change the local filename.
        # The generated snapshot is an optional data input, not a shipped asset.
        if local_path != "summary_data.js":
            assert (VIEW / local_path).is_file(), path


def test_read_only_page_controls_have_accessible_names_and_types():
    parsed = Tags()
    parsed.feed((VIEW / "activity.html").read_text())
    controls = {attrs.get("id"): (tag, attrs) for tag, attrs in parsed.tags if tag in {"input", "button", "select"}}
    assert controls["activity-search"][1]["type"] == "search"
    assert controls["actor-filter"][0] == controls["skill-filter"][0] == "select"
    assert controls["auto-refresh"][1]["type"] == "checkbox"
    assert all(attrs.get("type") == "button" for tag, attrs in controls.values() if tag == "button")
    assert any(tag == "a" and attrs.get("href") == "#activity-root" for tag, attrs in parsed.tags)
    assert any(attrs.get("id") == "data-announcement" and attrs.get("role") == "status" for _, attrs in parsed.tags)
