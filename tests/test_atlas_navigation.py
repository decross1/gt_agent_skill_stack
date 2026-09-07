"""Cross-page navigation and offline asset contract for the Atlas workspace.

Behavioral page tests exercise the handlers; this checks that every existing
entry URL reaches the same shell, including the contextual review destination.
"""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

import pytest

VIEW = Path(__file__).resolve().parents[1] / "memory/brain/view"
PAGES = ("dashboard.html", "graph.html", "activity.html", "proposal_review.html")
DESTINATIONS = [
    ("dashboard.html", "Today"),
    ("graph.html", "Work graph"),
    ("activity.html", "Skills & healing"),
]


class Shell(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.in_primary = False
        self.links = []
        self.active_link = None
        self.assets = []
        self.root = {}
        self.theme_buttons = []
        self.feed(text)

    def handle_starttag(self, tag, pairs):
        attrs = dict(pairs)
        if tag == "html":
            self.root = attrs
        if tag == "nav" and attrs.get("aria-label") == "Primary":
            self.in_primary = True
        if tag == "a" and self.in_primary:
            self.active_link = {"attrs": attrs, "text": ""}
            self.links.append(self.active_link)
        if tag == "button" and "data-atlas-theme" in attrs:
            self.theme_buttons.append(attrs)
        if tag == "script" and attrs.get("src"):
            self.assets.append((attrs["src"], attrs))
        if tag == "link" and attrs.get("rel") == "stylesheet":
            self.assets.append((attrs["href"], attrs))

    def handle_data(self, data):
        if self.active_link is not None:
            self.active_link["text"] += data

    def handle_endtag(self, tag):
        if tag == "a":
            self.active_link = None
        if tag == "nav":
            self.in_primary = False


@pytest.mark.parametrize("page", PAGES)
def test_old_entry_urls_have_three_named_primary_destinations(page):
    shell = Shell((VIEW / page).read_text())
    assert [(a["attrs"].get("href"), a["text"].strip()) for a in shell.links] == DESTINATIONS
    for href, _ in DESTINATIONS:
        assert (VIEW / href).is_file()
    selected = [a for a in shell.links if a["attrs"].get("aria-current")]
    assert len(selected) == 1
    target = "activity.html" if page == "proposal_review.html" else page
    assert selected[0]["attrs"]["href"] == target
    assert selected[0]["attrs"]["aria-current"] == ("location" if page == "proposal_review.html" else "page")


@pytest.mark.parametrize("page", PAGES)
def test_light_default_and_versioned_local_theme_assets_are_available(page):
    shell = Shell((VIEW / page).read_text())
    assert "data-atlas" in shell.root
    assert shell.root.get("data-theme") == "light"
    assert len(shell.theme_buttons) == 1
    assert shell.theme_buttons[0].get("type") == "button"
    assets = {urlsplit(src).path: (src, attrs) for src, attrs in shell.assets}
    for name in ("atlas.css", "atlas.js"):
        src, attrs = assets[name]
        assert urlsplit(src).query, f"{page} must version its shared presentation dependency"
        assert not urlsplit(src).netloc
        assert (VIEW / name).is_file()
    assert "async" in assets["atlas.js"][1] and "defer" not in assets["atlas.js"][1], "optional theme must not gate DOMContentLoaded"


def test_all_destinations_use_one_shared_theme_revision():
    references = []
    for page in PAGES:
        shell = Shell((VIEW / page).read_text())
        references.append(tuple(sorted(src for src, _ in shell.assets if urlsplit(src).path in ("atlas.css", "atlas.js"))))
    assert len(references[0]) == 2
    assert len(set(references)) == 1
