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
        self.in_primary = False
        self.primary_links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.tags.append((tag, attrs))
        if tag == "nav" and attrs.get("aria-label") == "Primary":
            self.in_primary = True
        elif tag == "a" and self.in_primary:
            self.primary_links.append(attrs)

    def handle_endtag(self, tag):
        if tag == "nav" and self.in_primary:
            self.in_primary = False


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
        # These two shared assets are supplied by the Today lane at integration.
        if local_path not in {"summary_data.js", "atlas.css", "atlas.js"}:
            assert (VIEW / local_path).is_file(), path


def test_activity_uses_the_three_destination_atlas_navigation():
    text = (VIEW / "activity.html").read_text()
    parsed = Tags()
    parsed.feed(text)
    html = next(attrs for tag, attrs in parsed.tags if tag == "html")
    assert "data-atlas" in html
    assert html["data-theme"] == "light"
    assert [link["href"] for link in parsed.primary_links] == [
        "dashboard.html", "graph.html", "activity.html"
    ]
    assert parsed.primary_links[-1]["aria-current"] == "page"
    assert text.index("activity.css?v=20260907-atlas") < text.index("atlas.css?v=20260907-a")
    assert any(tag == "script" and attrs.get("src") == "atlas.js?v=20260907-a" and
               "defer" in attrs for tag, attrs in parsed.tags)


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
