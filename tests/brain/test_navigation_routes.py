"""Socketless route regressions for the Atlas workspace entry points.

The real Handler is driven against a private view fixture.  No listener,
service, model, API action, or canonical Brain file is involved.
"""
from io import BytesIO
from pathlib import Path
import sys

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

import brain_server as bs  # noqa: E402


@pytest.fixture
def private_view(tmp_path):
    (tmp_path / "dashboard.html").write_text("TODAY\n")
    (tmp_path / "asset.txt").write_text("static body\n")
    archive = tmp_path / "mockups"
    archive.mkdir()
    for name in ("m1.html", "m2.html", "m3.html"):
        (archive / name).write_text(name + "\n")
    (archive / "SPEC.md").write_text("historical source notes\n")
    return tmp_path


def request(private_view, path, method="GET"):
    """Drive the actual Handler without constructing a socket-backed server."""
    handler = bs.Handler.__new__(bs.Handler)
    handler.directory = str(private_view)
    handler.path = path
    handler.command = method
    handler.request_version = "HTTP/1.1"
    handler.headers = {}
    handler.wfile = BytesIO()
    observed = {"headers": []}
    handler.send_response = lambda code, message=None: observed.update(code=code)
    handler.send_header = lambda name, value: observed["headers"].append((name, value))
    handler.end_headers = lambda: None

    if method == "HEAD":
        handler.do_HEAD()
    else:
        handler.do_GET()
    observed["body"] = handler.wfile.getvalue()
    observed["headers"] = dict(observed["headers"])
    return observed


@pytest.mark.parametrize(
    ("path", "location"),
    [
        ("/", "/dashboard.html"),
        ("/?window=3", "/dashboard.html?window=3"),
        ("/index.html?window=7#recorded-blockers", "/dashboard.html?window=7#recorded-blockers"),
    ],
)
@pytest.mark.parametrize("method", ["GET", "HEAD"])
def test_workspace_entries_redirect_to_today_on_the_same_origin(
        private_view, path, location, method):
    response = request(private_view, path, method)
    assert response["code"] == 302
    assert response["headers"]["Location"] == location
    assert response["headers"]["Content-Length"] == "0"
    assert response["body"] == b""


def test_mockup_directory_is_a_labelled_source_archive_with_atlas_return(private_view):
    response = request(private_view, "/mockups/")
    body = response["body"].decode()
    assert response["code"] == 200
    assert "Archived mockups" in body
    assert "source-only" in body
    assert 'href="/dashboard.html"' in body
    for name in ("m1.html", "m2.html", "m3.html", "SPEC.md"):
        assert f'href="{name}"' in body


def test_unrelated_static_get_keeps_the_standard_handler_body(private_view):
    response = request(private_view, "/asset.txt?download=1")
    assert response["code"] == 200
    assert response["body"] == b"static body\n"
    assert response["headers"]["Content-Length"] == str(len(response["body"]))
