"""Offline tests for the reusable W3C browser navigation boundary."""

from __future__ import annotations

import http.server
import json
import socket
import sys
import threading
import urllib.error
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from browser_navigation import (  # noqa: E402
    W3C_ELEMENT_KEY,
    BrowserCleanup,
    FirefoxNavigation,
    NavigationTimeout,
    WebDriverClient,
    WebDriverCommandError,
    allocate_loopback_ports,
    cleanup_is_qualified,
    path_is_within,
    port_is_closed,
    wait_until,
)


class _Clock:
    def __init__(self):
        self.value = 0.0

    def now(self):
        return self.value

    def sleep(self, seconds):
        self.value += seconds


def test_wait_treats_null_and_nonobjects_as_transient():
    states = iter([None, [], "loading", {"readyState": "complete"}])
    clock = _Clock()
    result = wait_until(
        lambda: next(states),
        lambda value: isinstance(value, dict) and value.get("readyState") == "complete",
        timeout=1,
        interval=0.1,
        clock=clock.now,
        sleep=clock.sleep,
    )
    assert result == {"readyState": "complete"}


def test_wait_has_strict_deadline_and_compact_last_value():
    clock = _Clock()
    with pytest.raises(NavigationTimeout, match="never ready") as failure:
        wait_until(lambda: {"payload": "x" * 5000}, lambda _value: False,
                   timeout=0.2, interval=0.1, description="never ready",
                   clock=clock.now, sleep=clock.sleep)
    assert len(str(failure.value)) < 900


class _ValueClient(WebDriverClient):
    def __init__(self, value):
        super().__init__("http://127.0.0.1:1")
        self.value = value

    def command(self, *_args, **_kwargs):
        return self.value


def test_execute_small_rejects_giant_returned_state():
    browser = object.__new__(FirefoxNavigation)
    browser.client = _ValueClient({"rows": ["x" * 1000] * 20})
    browser.session_id = "test-session"
    with pytest.raises(ValueError, match="exceeded 1024 bytes"):
        browser.execute_small("return window.state", max_bytes=1024)


class _ElementClient(WebDriverClient):
    def __init__(self):
        super().__init__("http://127.0.0.1:1")
        self.calls = []

    def command(self, method, path, payload=None, **_kwargs):
        self.calls.append((method, path, payload))
        if path.endswith("/element"):
            return {W3C_ELEMENT_KEY: "fresh-element"}
        if path.endswith("/displayed"):
            return True
        if path.endswith("/click"):
            return None
        raise AssertionError(path)


def test_visible_click_uses_fresh_w3c_element_endpoints():
    browser = object.__new__(FirefoxNavigation)
    browser.client = _ElementClient()
    browser.session_id = "session-1"
    element = browser.click_visible("#choice")
    assert element == "fresh-element"
    assert browser.client.calls == [
        ("POST", "/session/session-1/element", {"using": "css selector", "value": "#choice"}),
        ("GET", "/session/session-1/element/fresh-element/displayed", None),
        ("POST", "/session/session-1/element/fresh-element/click", {}),
    ]


def test_port_plan_is_unique_loopback_and_excludes_default_bidi():
    ports = allocate_loopback_ports(3)
    assert len(set(ports)) == 3
    assert 9222 not in ports
    assert all(port_is_closed(port) for port in ports)


def test_startup_retries_only_live_process_connection_refusal():
    class Client:
        def command(self, *_args, **_kwargs):
            raise urllib.error.URLError(ConnectionRefusedError(111, "connection refused"))

    class Process:
        def __init__(self, result):
            self.result = result

        def poll(self):
            return self.result

    browser = object.__new__(FirefoxNavigation)
    browser.client, browser.driver_process = Client(), Process(None)
    assert browser._read_driver_status() is None
    browser.driver_process = Process(2)
    with pytest.raises(urllib.error.URLError):
        browser._read_driver_status()


def test_cleanup_qualification_requires_owned_profile_and_every_signal(tmp_path):
    owned = tmp_path / "root" / "profile"
    outside = tmp_path / "outside"
    assert path_is_within(owned, tmp_path / "root")
    assert not path_is_within(outside, tmp_path / "root")
    cleanup = BrowserCleanup(
        session_deleted=True,
        profile_within_root=True,
        profile_removed=True,
        profile_root_within_parent=True,
        profile_root_removed=True,
        ports_closed={"webdriver": True, "marionette": True, "bidi": True},
        errors=[],
    )
    assert cleanup_is_qualified(cleanup)
    cleanup.profile_within_root = False
    assert not cleanup_is_qualified(cleanup)


def test_w3c_client_decodes_values_and_preserves_remote_errors():
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *_args):
            return

        def do_GET(self):  # noqa: N802
            if self.path == "/ok":
                status, data = 200, json.dumps({"value": {"ready": True}}).encode()
            elif self.path == "/invalid":
                status, data = 200, b"{"
            else:
                status = 500
                data = json.dumps({"value": {"error": "javascript error", "message": "exact failure"}}).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client = WebDriverClient(f"http://127.0.0.1:{server.server_port}")
        assert client.command("GET", "/ok") == {"ready": True}
        with pytest.raises(WebDriverCommandError, match="exact failure") as failure:
            client.command("GET", "/error")
        assert failure.value.error == "javascript error"
        with pytest.raises(WebDriverCommandError, match="invalid response") as invalid:
            client.command("GET", "/invalid")
        assert invalid.value.status == 200
        assert [row["status"] for row in client.commands] == [200, 500, 200]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
