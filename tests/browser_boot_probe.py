#!/usr/bin/env python3
"""Finite Firefox probe for the Brain Dashboard and Graph bootstrap.

The probe serves checkout-owned HTML/scripts with caller-supplied saved projection
data.  It never calls a page renderer or injects projection data.  WebDriver uses
``pageLoadStrategy=none`` so a deliberately delayed classic script cannot hang the
probe itself.  Every delayed response is finite and every process started here is
cleaned up here.

Example (private fixture paths are deliberately caller supplied)::

    python3 tests/browser_boot_probe.py \
      --source "$PWD" --fixture-view /path/to/saved/view \
      --profile-root /path/firefox/can/read --output /path/to/receipts \
      --phase candidate --stale-ui-revision REV
"""

from __future__ import annotations

import argparse
import base64
import dataclasses
import hashlib
import http.server
import json
import math
import mimetypes
import queue
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit


PAGES = ("dashboard.html", "graph.html")
CLASSIC_ASSETS = ("summary_data.js", "map_data.js", "ui.js", "map.js")


def utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_line(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class ReceiptWriter:
    def __init__(self, output: Path) -> None:
        self.output = output
        self._lock = threading.Lock()
        self._raw = (output / "raw-output.jsonl").open("a", encoding="utf-8", buffering=1)

    def emit(self, event: str, **fields: Any) -> None:
        row = {"timestamp": utc_now(), "event": event, **fields}
        line = json_line(row)
        with self._lock:
            self._raw.write(line + "\n")
            self._raw.flush()
            print(line, flush=True)

    def close(self) -> None:
        self._raw.close()


@dataclasses.dataclass
class ProbeCase:
    page: str
    mode: str
    asset: str | None = None
    case_id: str = ""
    hold_started: threading.Event = dataclasses.field(default_factory=threading.Event)
    hold_started_at: float | None = None
    hold_release_at: float | None = None

    def __post_init__(self) -> None:
        if self.page not in PAGES:
            raise ValueError(f"unsupported page: {self.page}")
        if self.mode in {"hold", "pagehide", "missing"} and self.asset not in CLASSIC_ASSETS:
            raise ValueError(f"{self.mode} needs one of {CLASSIC_ASSETS}, got {self.asset!r}")
        if self.mode not in {
            "normal",
            "hold",
            "pagehide",
            "missing",
            "stale-ui",
            "file",
            "file-missing-ui",
        }:
            raise ValueError(f"unsupported mode: {self.mode}")
        stem = self.page.removesuffix(".html")
        suffix = "-" + self.asset.removesuffix(".js").replace("_", "-") if self.asset else ""
        self.case_id = re.sub(r"[^a-z0-9-]", "-", f"{stem}-{self.mode}{suffix}".lower())


def parse_assignment(data: bytes) -> Any:
    text = data.decode("utf-8")
    eq = text.find("=")
    if eq < 0:
        raise ValueError("fixture JavaScript has no assignment")
    value, _ = json.JSONDecoder().raw_decode(text[eq + 1 :].lstrip())
    return value


def available_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def read_stale_ui(args: argparse.Namespace, source: Path) -> tuple[bytes | None, dict[str, Any]]:
    if args.stale_ui:
        path = Path(args.stale_ui).resolve()
        data = path.read_bytes()
        return data, {"kind": "path", "value": str(path), "sha256": sha256_bytes(data)}
    if args.stale_ui_revision:
        ref = args.stale_ui_revision
        proc = subprocess.run(
            ["git", "-C", str(source), "show", f"{ref}:memory/brain/view/ui.js"],
            check=True,
            capture_output=True,
        )
        data = proc.stdout
        return data, {"kind": "git-revision", "value": ref, "sha256": sha256_bytes(data)}
    return None, {"kind": "none"}


def parse_cases(args: argparse.Namespace, stale_ui: bytes | None) -> list[ProbeCase]:
    pages = args.page or list(PAGES)
    specs = args.case or []
    if not specs:
        specs = ["normal"]
        specs.extend(f"hold:{asset}" for asset in CLASSIC_ASSETS)
        specs.append("missing:ui.js")
        specs.append("missing:map.js")
        if stale_ui is not None:
            specs.append("stale-ui")
        if not args.skip_file_mode:
            specs.extend(("file", "file-missing-ui"))
        if not args.skip_pagehide:
            specs.append("pagehide:ui.js")
    cases: list[ProbeCase] = []
    seen: set[str] = set()
    for page in pages:
        for spec in specs:
            mode, _, asset = spec.partition(":")
            asset = asset or None
            if mode == "missing" and asset == "map.js" and page != "graph.html":
                continue
            if mode == "stale-ui" and stale_ui is None:
                raise ValueError("stale-ui case requires --stale-ui or --stale-ui-revision")
            case = ProbeCase(page=page, mode=mode, asset=asset)
            if case.case_id in seen:
                raise ValueError(f"duplicate case: {case.case_id}")
            seen.add(case.case_id)
            cases.append(case)
    return cases


class Fixture:
    def __init__(
        self,
        source_view: Path,
        fixture_view: Path,
        cases: list[ProbeCase],
        stale_ui: bytes | None,
        hold_seconds: float,
        output: Path,
    ) -> None:
        self.source_view = source_view
        self.fixture_view = fixture_view
        self.cases = {case.case_id: case for case in cases}
        self.stale_ui = stale_ui
        self.hold_seconds = hold_seconds
        self.events: list[dict[str, Any]] = []
        self.lock = threading.Lock()
        self.request_number = 0
        self.summary = parse_assignment((fixture_view / "summary_data.js").read_bytes())
        self.map = parse_assignment((fixture_view / "map_data.js").read_bytes())
        self.log = (output / "network-server.jsonl").open("a", encoding="utf-8", buffering=1)

    def record(self, event: str, **fields: Any) -> None:
        row = {"timestamp": utc_now(), "event": event, **fields}
        with self.lock:
            self.events.append(row)
            self.log.write(json_line(row) + "\n")
            self.log.flush()

    def next_request_id(self) -> int:
        with self.lock:
            self.request_number += 1
            return self.request_number

    def bytes_for(self, case: ProbeCase, asset: str) -> tuple[int, str, bytes]:
        if case.mode == "missing" and asset == case.asset:
            return 404, "text/plain; charset=utf-8", b"missing fixture dependency\n"
        if case.mode == "stale-ui" and asset == "ui.js":
            assert self.stale_ui is not None
            return 200, "text/javascript; charset=utf-8", self.stale_ui
        if asset == "api/summary":
            return 200, "application/json", json.dumps(self.summary).encode("utf-8")
        if asset == "api/map":
            return 200, "application/json", json.dumps(self.map).encode("utf-8")
        if asset == "api/operations":
            return 503, "application/json", b'{"error":"fixture has no operations snapshot"}'
        # HTTP paths are caller input even on this finite loopback fixture.
        # All supported static assets are direct children of the copied view.
        if asset in {"", ".", ".."} or Path(asset).name != asset:
            return 404, "text/plain; charset=utf-8", b"unsupported fixture path\n"
        if asset in {"summary_data.js", "map_data.js"}:
            path = self.fixture_view / asset
        else:
            path = self.source_view / asset
        if not path.is_file():
            return 404, "text/plain; charset=utf-8", b"fixture path not found\n"
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if mime in {"text/html", "text/css", "text/javascript", "application/javascript"}:
            mime += "; charset=utf-8"
        return 200, mime, path.read_bytes()

    def close(self) -> None:
        self.log.close()


class FiniteThreadingHTTPServer(http.server.ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False


def start_fixture_server(fixture: Fixture) -> tuple[FiniteThreadingHTTPServer, threading.Thread]:
    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_args: Any) -> None:
            return

        def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
            self._respond(head_only=False)

        def do_HEAD(self) -> None:  # noqa: N802 - stdlib handler API
            self._respond(head_only=True)

        def _respond(self, head_only: bool) -> None:
            request_id = fixture.next_request_id()
            parsed = urlsplit(self.path)
            parts = [unquote(part) for part in parsed.path.split("/") if part]
            case_id = parts[0] if parts else ""
            asset = "/".join(parts[1:]) if len(parts) > 1 else ""
            case = fixture.cases.get(case_id)
            fixture.record(
                "request-started",
                request_id=request_id,
                method=self.command,
                raw_path=self.path,
                case_id=case_id,
                asset=asset,
            )
            if case is None:
                status, mime, body = 404, "text/plain; charset=utf-8", b"unknown fixture case\n"
            else:
                if case.mode in {"hold", "pagehide"} and asset == case.asset:
                    now = time.monotonic()
                    with fixture.lock:
                        if case.hold_started_at is None:
                            case.hold_started_at = now
                            case.hold_release_at = now + fixture.hold_seconds
                            first = True
                        else:
                            first = False
                        release_at = case.hold_release_at
                    if first:
                        case.hold_started.set()
                        fixture.record(
                            "hold-started",
                            request_id=request_id,
                            case_id=case_id,
                            asset=asset,
                            hold_seconds=fixture.hold_seconds,
                        )
                    assert release_at is not None
                    remaining = release_at - time.monotonic()
                    if remaining > 0:
                        time.sleep(remaining)
                    fixture.record(
                        "hold-released", request_id=request_id, case_id=case_id, asset=asset
                    )
                status, mime, body = fixture.bytes_for(case, asset)
            try:
                self.send_response(status)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("Connection", "close")
                self.end_headers()
                if not head_only:
                    self.wfile.write(body)
                fixture.record(
                    "response-completed",
                    request_id=request_id,
                    case_id=case_id,
                    asset=asset,
                    status=status,
                    bytes=len(body),
                    sha256=sha256_bytes(body),
                )
            except (BrokenPipeError, ConnectionResetError) as error:
                fixture.record(
                    "response-write-failed",
                    request_id=request_id,
                    case_id=case_id,
                    asset=asset,
                    error=type(error).__name__,
                )

    server = FiniteThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, name="browser-probe-fixture", daemon=True)
    thread.start()
    return server, thread


class WebDriver:
    def __init__(self, base: str) -> None:
        self.base = base
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def command(self, method: str, path: str, value: Any = None, timeout: float = 20) -> Any:
        data = None if value is None else json.dumps(value).encode("utf-8")
        request = urllib.request.Request(
            self.base + path,
            data=data,
            method=method,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        status = 0
        raw = b""
        try:
            with self.opener.open(request, timeout=timeout) as response:
                status = response.status
                raw = response.read()
        except urllib.error.HTTPError as error:
            status = error.code
            raw = error.read()
        parsed = json.loads(raw or b"{}")
        if status >= 400:
            raise RuntimeError(f"WebDriver {method} {path} returned {status}: {parsed}")
        return parsed.get("value")


class BidiBridge:
    NODE_PROGRAM = r"""
const ws = new WebSocket(process.argv[1]);
const send = value => process.stdout.write(JSON.stringify(value) + "\n");
ws.onopen = () => send({received_at:new Date().toISOString(),bridge:"ready"});
ws.onmessage = event => {
  let payload;
  try { payload = JSON.parse(event.data); }
  catch (error) { payload = {type:"bridge-parse-error",raw:String(event.data),error:String(error)}; }
  send({received_at:new Date().toISOString(),payload});
};
ws.onerror = event => process.stderr.write("WebSocket error " + String(event.message || event.type || event) + "\n");
ws.onclose = event => send({received_at:new Date().toISOString(),bridge:"closed",code:event.code,reason:event.reason});
require("readline").createInterface({input:process.stdin}).on("line", line => {
  if (ws.readyState !== WebSocket.OPEN) {
    send({received_at:new Date().toISOString(),bridge:"send-rejected",ready_state:ws.readyState});
    return;
  }
  ws.send(line);
});
"""

    def __init__(self, node: str, websocket_url: str, output: Path) -> None:
        self.stderr = (output / "bidi-bridge.stderr.log").open("w", encoding="utf-8")
        self.raw = (output / "bidi-raw.jsonl").open("w", encoding="utf-8", buffering=1)
        self.process = subprocess.Popen(
            [node, "-e", self.NODE_PROGRAM, websocket_url],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self.stderr,
            text=True,
            bufsize=1,
        )
        self.inbox: queue.Queue[dict[str, Any]] = queue.Queue()
        self.events: list[dict[str, Any]] = []
        self.responses: dict[int, dict[str, Any]] = {}
        self.message_id = 0
        self.reader = threading.Thread(target=self._read, name="browser-probe-bidi", daemon=True)
        self.reader.start()
        try:
            ready = self.inbox.get(timeout=10)
            if ready.get("bridge") != "ready":
                raise RuntimeError(f"BiDi bridge did not open: {ready}")
        except BaseException:
            self.close()
            raise

    def _read(self) -> None:
        assert self.process.stdout is not None
        for line in self.process.stdout:
            self.raw.write(line)
            self.raw.flush()
            try:
                self.inbox.put(json.loads(line))
            except json.JSONDecodeError:
                self.inbox.put({"bridge": "invalid-json", "raw": line})
        self.inbox.put({"bridge": "eof"})

    def _route(self, item: dict[str, Any]) -> None:
        payload = item.get("payload")
        if isinstance(payload, dict) and isinstance(payload.get("id"), int):
            self.responses[payload["id"]] = item
        else:
            self.events.append(item)

    def command(self, method: str, params: dict[str, Any], timeout: float = 15) -> dict[str, Any]:
        self.message_id += 1
        message_id = self.message_id
        assert self.process.stdin is not None
        self.process.stdin.write(json.dumps({"id": message_id, "method": method, "params": params}) + "\n")
        self.process.stdin.flush()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if message_id in self.responses:
                item = self.responses.pop(message_id)
                payload = item["payload"]
                if payload.get("type") == "error":
                    raise RuntimeError(f"BiDi {method} failed: {payload}")
                return payload
            try:
                item = self.inbox.get(timeout=min(0.5, max(0.01, deadline - time.monotonic())))
            except queue.Empty:
                continue
            if item.get("bridge") in {"eof", "closed", "send-rejected", "invalid-json"}:
                raise RuntimeError(f"BiDi bridge failure: {item}")
            self._route(item)
        raise TimeoutError(f"BiDi command timed out: {method}")

    def flush(self) -> None:
        self.command("session.status", {})
        while True:
            try:
                item = self.inbox.get_nowait()
            except queue.Empty:
                break
            self._route(item)

    def close(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        self.reader.join(timeout=2)
        self.raw.close()
        self.stderr.close()


CAPTURE_SCRIPT = r"""
const status = document.getElementById('data-source-status');
const canvas = document.getElementById('map');
return {
  observedAt: new Date().toISOString(),
  url: location.href,
  title: document.title,
  readyState: document.readyState,
  status: status ? status.textContent : null,
  statusRole: status ? status.getAttribute('role') : null,
  bodyText: document.body ? document.body.innerText : null,
  probe: window.__browserBootProbe || null,
  uiKeys: Object.keys(window.UI || {}).sort(),
  hasSummary: !!window.BRAIN_SUMMARY,
  hasMap: !!window.BRAIN_MAP,
  statusRows: document.getElementById('status')?.children.length ?? null,
  canvas: canvas ? {width:canvas.width,height:canvas.height,clientWidth:canvas.clientWidth,clientHeight:canvas.clientHeight,
    rendererMounted:!!canvas.__brainmap} : null,
  mapNoteHidden: document.getElementById('mapnote')?.hidden ?? null,
  resources: performance.getEntriesByType('resource').map(entry => ({
    name: entry.name,
    initiatorType: entry.initiatorType,
    duration: entry.duration,
    transferSize: entry.transferSize,
    decodedBodySize: entry.decodedBodySize,
    responseStatus: entry.responseStatus
  })),
  userAgent: navigator.userAgent
};
"""


PRELOAD_FUNCTION = r"""() => {
  const state = globalThis.__browserBootProbe = {
    installedAt: new Date().toISOString(), errors: [], lifecycle: []
  };
  const note = (type, extra = {}) => state.lifecycle.push({type, at:new Date().toISOString(), ...extra});
  addEventListener('error', event => state.errors.push({
    type:'error', at:new Date().toISOString(), message:event.message || 'resource load failed',
    file:event.filename || event.target?.src || '', line:event.lineno || 0,
    stack:String(event.error?.stack || '')
  }), true);
  addEventListener('unhandledrejection', event => state.errors.push({
    type:'unhandledrejection', at:new Date().toISOString(), message:String(event.reason || ''),
    stack:String(event.reason?.stack || '')
  }));
  document.addEventListener('readystatechange', () => note('readystatechange', {readyState:document.readyState}));
  document.addEventListener('DOMContentLoaded', () => note('DOMContentLoaded'));
  addEventListener('load', () => note('load'));
  addEventListener('pagehide', event => note('pagehide', {persisted:event.persisted}));
  addEventListener('pageshow', event => note('pageshow', {persisted:event.persisted}));
}"""


def execute(driver: WebDriver, session: str, script: str, timeout: float = 15) -> Any:
    return driver.command(
        "POST",
        f"/session/{session}/execute/sync",
        {"script": script, "args": []},
        timeout=timeout,
    )


def wait_until(deadline: float) -> None:
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        time.sleep(min(0.1, remaining))


def wait_for_dom(driver: WebDriver, session: str, expected_url: str, timeout: float = 5) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            state = execute(
                driver,
                session,
                "return {url:location.href,ready:!!document.body && !!document.getElementById('data-source-status')};",
                5,
            )
            if state.get("url") == expected_url and state.get("ready"):
                return
        except Exception as error:  # navigation can transiently replace the realm
            last_error = error
        time.sleep(0.05)
    raise TimeoutError(f"page DOM did not become inspectable: {last_error}")


def capture(
    driver: WebDriver,
    bidi: BidiBridge,
    session: str,
    output: Path,
    case: ProbeCase,
    moment: str,
    receipts: ReceiptWriter,
) -> dict[str, Any]:
    bidi.flush()
    data = execute(driver, session, CAPTURE_SCRIPT)
    data.update({"caseId": case.case_id, "page": case.page, "mode": case.mode, "asset": case.asset, "moment": moment})
    target = output / f"{case.case_id}.{moment}.json"
    target.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    encoded = driver.command("GET", f"/session/{session}/screenshot", timeout=20)
    png = base64.b64decode(encoded)
    png_path = output / f"{case.case_id}.{moment}.png"
    png_path.write_bytes(png)
    receipts.emit(
        "capture",
        case_id=case.case_id,
        moment=moment,
        ready_state=data.get("readyState"),
        status=data.get("status"),
        errors=len((data.get("probe") or {}).get("errors") or []),
        json=str(target),
        png=str(png_path),
        png_sha256=sha256_bytes(png),
    )
    return data


def status_kind(data: dict[str, Any]) -> str:
    status = str(data.get("status") or "").strip()
    lower = status.lower()
    if not status or "not been checked" in lower:
        return "unchecked"
    if any(word in lower for word in ("could not start", "failed", "timed out", "timeout", "unable to start")):
        return "failure"
    if any(word in lower for word in ("snapshot", "live response", "mixed data", "cached live", "data incomplete")):
        return "supported-data"
    return "other"


def api_request_count(fixture: Fixture, case_id: str) -> int:
    with fixture.lock:
        return sum(
            row.get("event") == "request-started"
            and row.get("case_id") == case_id
            and str(row.get("asset", "")).startswith("api/")
            for row in fixture.events
        )


def verdict_for(
    case: ProbeCase,
    phase: str,
    captures: dict[str, dict[str, Any]],
    fixture: Fixture,
) -> tuple[bool, str, dict[str, Any]]:
    kinds = {name: status_kind(data) for name, data in captures.items()}
    details = {"status_kinds": kinds, "api_request_count": api_request_count(fixture, case.case_id)}
    if case.mode in {"hold", "pagehide"}:
        first_name = "after-pagehide" if case.mode == "pagehide" else "deadline"
        first = captures[first_name]
        released = captures["released"]
        if phase == "baseline":
            passed = (status_kind(first) == "unchecked" and released.get("readyState") == "complete"
                      and status_kind(released) in {"supported-data", "failure"})
            details["baseline_hold_transition"] = case.mode == "hold" and passed
            reason = "baseline parser block reproduced, then released" if passed else "baseline parser block was not reproduced"
            return passed, reason, details
        if phase == "candidate":
            same_failure = status_kind(first) == "failure" and status_kind(released) == "failure" and first.get("status") == released.get("status")
            no_boot_requests = details["api_request_count"] == 0
            passed = same_failure and no_boot_requests
            reason = "bounded failure stayed terminal after late release" if passed else "late release changed failure or application booted"
            return passed, reason, details
        passed = status_kind(first) != "unchecked"
        return passed, "observation reached a terminal status" if passed else "status remained unchecked", details
    final = captures["final"]
    kind = status_kind(final)
    if phase == "baseline":
        passed = True
        reason = "baseline observation recorded"
    elif case.mode in {"normal", "file"}:
        canvas = final.get("canvas") or {}
        rendered = (
            (final.get("statusRows") or 0) > 0 if case.page == "dashboard.html"
            else canvas.get("width", 0) > 0 and canvas.get("height", 0) > 0
            and final.get("mapNoteHidden") is True and canvas.get("rendererMounted") is True
        )
        passed = (kind == "supported-data" and final.get("readyState") == "complete"
                  and rendered and not (final.get("probe") or {}).get("errors"))
        reason = "supported data rendered" if passed else "normal startup did not reach supported data"
    elif case.mode == "file-missing-ui":
        if case.page == "dashboard.html":
            passed = kind == "failure"
            reason = (
                "missing file-mode Dashboard interface produced an explicit failure"
                if passed
                else "missing file-mode Dashboard interface was not rejected"
            )
        else:
            status = str(final.get("status") or "").lower()
            passed = (
                urlsplit(str(final.get("url") or "")).scheme == "file"
                and status.startswith("saved data only")
                and "live refresh" in status
                and "source checks are disabled" in status
                and bool(final.get("hasSummary"))
                and bool(final.get("hasMap"))
                and (final.get("canvas") or {}).get("rendererMounted") is True
            )
            reason = (
                "file-mode Graph rendered explicitly qualified saved data"
                if passed
                else "file-mode Graph fallback was absent or overclaimed"
            )
    elif case.mode == "missing":
        passed = kind == "failure"
        reason = "missing dependency produced an explicit failure" if passed else "missing dependency was not reported as failure"
    elif case.mode == "stale-ui":
        passed = kind == "failure"
        reason = "stale interface produced an explicit failure" if passed else "stale interface was not rejected"
    else:
        passed = kind in {"failure", "supported-data"}
        reason = "dependency outcome is visible and bounded" if passed else "dependency outcome stayed unchecked"
    return passed, reason, details


def make_file_fixture(
    source_view: Path,
    fixture_view: Path,
    root: Path,
    omitted: frozenset[str] = frozenset(),
) -> Path:
    target = Path(tempfile.mkdtemp(prefix="browser-boot-file-", dir=root))
    for path in source_view.iterdir():
        if path.is_file() and path.name not in omitted:
            shutil.copy2(path, target / path.name)
    for name in ("summary_data.js", "map_data.js"):
        shutil.copy2(fixture_view / name, target / name)
    return target


def snapshot_source_view(source_view: Path, root: Path) -> Path:
    """Copy the served source once so a run cannot observe a mixed edit."""
    target = Path(tempfile.mkdtemp(prefix="browser-boot-source-", dir=root))
    for path in source_view.iterdir():
        if path.is_file():
            shutil.copy2(path, target / path.name)
    return target


def run_case(
    case: ProbeCase,
    phase: str,
    origin: str,
    fixture: Fixture,
    file_fixtures: dict[str, Path],
    driver: WebDriver,
    bidi: BidiBridge,
    session: str,
    output: Path,
    receipts: ReceiptWriter,
    observe_seconds: float,
    release_settle_seconds: float,
) -> dict[str, Any]:
    started = time.monotonic()
    receipts.emit("case-started", case_id=case.case_id, page=case.page, mode=case.mode, asset=case.asset)
    if case.mode in {"file", "file-missing-ui"}:
        file_fixture = file_fixtures[case.mode]
        url = (file_fixture / case.page).as_uri() + f"?probe={case.case_id}"
    else:
        url = f"{origin}/{case.case_id}/{case.page}"
    driver.command("POST", f"/session/{session}/url", {"url": url})
    wait_for_dom(driver, session, url)
    captures: dict[str, dict[str, Any]] = {}
    if case.mode in {"hold", "pagehide"}:
        if not case.hold_started.wait(timeout=5):
            raise TimeoutError(f"held resource was not requested: {case.case_id}")
        assert case.hold_started_at is not None and case.hold_release_at is not None
        if case.mode == "pagehide":
            dispatch_at = case.hold_started_at + min(2.0, observe_seconds / 2)
            wait_until(dispatch_at)
            execute(
                driver,
                session,
                "window.dispatchEvent(new PageTransitionEvent('pagehide',{persisted:false})); return true;",
            )
            time.sleep(0.25)
            captures["after-pagehide"] = capture(driver, bidi, session, output, case, "after-pagehide", receipts)
        else:
            wait_until(case.hold_started_at + observe_seconds)
            captures["deadline"] = capture(driver, bidi, session, output, case, "deadline", receipts)
        wait_until(case.hold_release_at + release_settle_seconds)
        captures["released"] = capture(driver, bidi, session, output, case, "released", receipts)
    else:
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            data = execute(driver, session, CAPTURE_SCRIPT)
            if data.get("readyState") == "complete" and status_kind(data) != "unchecked":
                break
            time.sleep(0.1)
        captures["final"] = capture(driver, bidi, session, output, case, "final", receipts)
    passed, reason, details = verdict_for(case, phase, captures, fixture)
    result = {
        "case_id": case.case_id,
        "page": case.page,
        "mode": case.mode,
        "asset": case.asset,
        "url": url,
        "phase": phase,
        "probe_pass": passed,
        "reason": reason,
        "details": details,
        "duration_ms": round((time.monotonic() - started) * 1000),
    }
    receipts.emit("case-finished", **result)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="repository checkout to test")
    parser.add_argument("--fixture-view", required=True, help="saved private view containing summary_data.js and map_data.js")
    parser.add_argument("--output", required=True, help="new or empty receipt directory")
    parser.add_argument("--profile-root", help="directory Firefox may use for temporary profile/file fixtures")
    parser.add_argument("--phase", choices=("observe", "baseline", "candidate"), default="observe")
    parser.add_argument("--page", action="append", choices=PAGES, help="page to test; repeatable")
    parser.add_argument(
        "--case",
        action="append",
        help=(
            "case: normal, hold:ASSET, pagehide:ASSET, missing:ASSET, "
            "stale-ui, file, or file-missing-ui; repeatable"
        ),
    )
    parser.add_argument("--stale-ui", help="saved stale ui.js path")
    parser.add_argument("--stale-ui-revision", help="git revision whose memory/brain/view/ui.js is served stale")
    parser.add_argument("--hold-seconds", type=float, default=8.0)
    parser.add_argument("--observe-seconds", type=float, default=5.75)
    parser.add_argument("--release-settle-seconds", type=float, default=1.25)
    parser.add_argument("--skip-file-mode", action="store_true")
    parser.add_argument("--skip-pagehide", action="store_true")
    parser.add_argument("--firefox", default="firefox")
    parser.add_argument("--geckodriver", default="geckodriver")
    parser.add_argument("--node", default="node")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not all(math.isfinite(value) and value > 0 for value in (
        args.hold_seconds, args.observe_seconds, args.release_settle_seconds
    )):
        raise SystemExit("probe delays must be finite positive numbers")
    if args.hold_seconds <= args.observe_seconds:
        raise SystemExit("--hold-seconds must exceed --observe-seconds")
    if args.stale_ui and args.stale_ui_revision:
        raise SystemExit("choose only one of --stale-ui and --stale-ui-revision")
    source = Path(args.source).resolve()
    fixture_view = Path(args.fixture_view).resolve()
    source_view = source / "memory" / "brain" / "view"
    for required in (*PAGES, "ui.js", "map.js"):
        if not (source_view / required).is_file():
            raise SystemExit(f"missing source asset: {source_view / required}")
    for required in ("summary_data.js", "map_data.js"):
        if not (fixture_view / required).is_file():
            raise SystemExit(f"missing fixture asset: {fixture_view / required}")
    output = Path(args.output).resolve()
    if output.exists() and any(output.iterdir()):
        raise SystemExit(f"output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    profile_root = Path(args.profile_root).resolve() if args.profile_root else Path(tempfile.gettempdir())
    profile_root.mkdir(parents=True, exist_ok=True)
    source_snapshot = snapshot_source_view(source_view, profile_root)
    receipts: ReceiptWriter | None = None
    try:
        stale_ui, stale_meta = read_stale_ui(args, source)
        cases = parse_cases(args, stale_ui)
        receipts = ReceiptWriter(output)
        fixture = Fixture(source_snapshot, fixture_view, cases, stale_ui, args.hold_seconds, output)
    except BaseException:
        if receipts is not None:
            receipts.close()
        shutil.rmtree(source_snapshot, ignore_errors=True)
        raise
    server: FiniteThreadingHTTPServer | None = None
    server_thread: threading.Thread | None = None
    driver_process: subprocess.Popen[str] | None = None
    driver_log = None
    bidi: BidiBridge | None = None
    session: str | None = None
    profile: Path | None = None
    file_fixtures: dict[str, Path] = {}
    results: list[dict[str, Any]] = []
    fatal: dict[str, Any] | None = None
    started = time.monotonic()
    metadata = {
        "started_at": utc_now(),
        "argv": sys.argv if argv is None else [sys.argv[0], *argv],
        "runner": {
            "path": str(Path(__file__).resolve()),
            "sha256": sha256_bytes(Path(__file__).read_bytes()),
        },
        "source": str(source),
        "source_head": subprocess.run(
            ["git", "-C", str(source), "rev-parse", "HEAD"], check=True, capture_output=True, text=True
        ).stdout.strip(),
        "source_snapshot_captured_at": utc_now(),
        "source_assets": {
            name: sha256_bytes((source_snapshot / name).read_bytes()) for name in (*PAGES, "ui.js", "map.js")
        },
        "fixture_view": str(fixture_view),
        "fixture_assets": {
            name: sha256_bytes((fixture_view / name).read_bytes()) for name in ("summary_data.js", "map_data.js")
        },
        "stale_ui": stale_meta,
        "phase": args.phase,
        "hold_seconds": args.hold_seconds,
        "observe_seconds": args.observe_seconds,
        "release_settle_seconds": args.release_settle_seconds,
        "manual_render_calls": 0,
        "projection_data_injections": 0,
        "cases": [],
    }
    # dataclasses.asdict cannot serialize threading.Event; replace the case list explicitly.
    metadata["cases"] = [
        {"case_id": case.case_id, "page": case.page, "mode": case.mode, "asset": case.asset}
        for case in cases
    ]
    receipts.emit("probe-started", source_head=metadata["source_head"], phase=args.phase, cases=len(cases))
    try:
        server, server_thread = start_fixture_server(fixture)
        origin = f"http://127.0.0.1:{server.server_port}"
        metadata["fixture_origin"] = origin
        profile = Path(tempfile.mkdtemp(prefix="browser-boot-firefox-", dir=profile_root))
        if any(case.mode == "file" for case in cases):
            file_fixtures["file"] = make_file_fixture(source_snapshot, fixture_view, profile_root)
        if any(case.mode == "file-missing-ui" for case in cases):
            file_fixtures["file-missing-ui"] = make_file_fixture(
                source_snapshot,
                fixture_view,
                profile_root,
                frozenset({"ui.js"}),
            )
        if file_fixtures:
            metadata["file_fixtures"] = {mode: str(path) for mode, path in file_fixtures.items()}
        webdriver_port = available_port()
        websocket_port = available_port()
        while websocket_port == webdriver_port:
            websocket_port = available_port()
        metadata["webdriver_port"] = webdriver_port
        metadata["geckodriver_websocket_port"] = websocket_port
        driver_log = (output / "geckodriver.log").open("w", encoding="utf-8")
        command = [
            args.geckodriver,
            "--host",
            "127.0.0.1",
            "--port",
            str(webdriver_port),
            "--websocket-port",
            str(websocket_port),
        ]
        driver_process = subprocess.Popen(command, stdout=driver_log, stderr=subprocess.STDOUT, text=True)
        metadata["owned_processes"] = {"geckodriver_pid": driver_process.pid}
        driver = WebDriver(f"http://127.0.0.1:{webdriver_port}")
        ready_deadline = time.monotonic() + 15
        while True:
            try:
                driver.command("GET", "/status", timeout=2)
                break
            except (urllib.error.URLError, ConnectionError, TimeoutError, json.JSONDecodeError):
                if driver_process.poll() is not None:
                    raise RuntimeError(f"geckodriver exited {driver_process.returncode}")
                if time.monotonic() >= ready_deadline:
                    raise TimeoutError("geckodriver did not become ready")
                time.sleep(0.1)
        firefox_args = ["-headless", "-profile", str(profile)]
        capabilities: dict[str, Any] = {
            "browserName": "firefox",
            "webSocketUrl": True,
            "pageLoadStrategy": "none",
            "moz:firefoxOptions": {"args": firefox_args},
        }
        if args.firefox != "firefox":
            capabilities["moz:firefoxOptions"]["binary"] = args.firefox
        created = driver.command("POST", "/session", {"capabilities": {"alwaysMatch": capabilities}}, timeout=35)
        session = created["sessionId"]
        metadata["browser_capabilities"] = created.get("capabilities", {})
        bidi = BidiBridge(args.node, created["capabilities"]["webSocketUrl"], output)
        metadata["owned_processes"]["bidi_bridge_pid"] = bidi.process.pid
        bidi.command(
            "session.subscribe",
            {
                "events": [
                    "log.entryAdded",
                    "network.beforeRequestSent",
                    "network.responseStarted",
                    "network.responseCompleted",
                    "network.fetchError",
                ]
            },
        )
        bidi.command("script.addPreloadScript", {"functionDeclaration": PRELOAD_FUNCTION})
        driver.command("POST", f"/session/{session}/timeouts", {"script": 15000, "pageLoad": 15000})
        driver.command("POST", f"/session/{session}/window/rect", {"width": 1440, "height": 1080})
        receipts.emit(
            "browser-started",
            browser=created["capabilities"].get("browserVersion"),
            user_agent=created["capabilities"].get("userAgent"),
            webdriver_port=webdriver_port,
            websocket_port=websocket_port,
        )
        for case in cases:
            results.append(
                run_case(
                    case,
                    args.phase,
                    origin,
                    fixture,
                    file_fixtures,
                    driver,
                    bidi,
                    session,
                    output,
                    receipts,
                    args.observe_seconds,
                    args.release_settle_seconds,
                )
            )
        bidi.flush()
    except Exception as error:
        fatal = {"type": type(error).__name__, "message": str(error), "traceback": traceback.format_exc()}
        receipts.emit("probe-fatal", error=fatal)
    finally:
        metadata["finished_at"] = utc_now()
        metadata["duration_ms"] = round((time.monotonic() - started) * 1000)
        metadata["server_request_events"] = len(fixture.events)
        if bidi is not None:
            metadata["bidi_event_envelopes"] = len(bidi.events)
        (output / "metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        if session is not None:
            try:
                driver.command("DELETE", f"/session/{session}", timeout=10)
            except Exception as cleanup_error:
                receipts.emit("cleanup-warning", target="webdriver-session", error=str(cleanup_error))
        if bidi is not None:
            bidi.close()
        if driver_process is not None and driver_process.poll() is None:
            driver_process.terminate()
            try:
                driver_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                driver_process.kill()
                driver_process.wait(timeout=5)
        if driver_log is not None:
            driver_log.close()
        if server is not None:
            server.shutdown()
            server.server_close()
        if server_thread is not None:
            server_thread.join(timeout=2)
        fixture.close()
        if profile is not None:
            shutil.rmtree(profile, ignore_errors=True)
        for file_fixture in file_fixtures.values():
            shutil.rmtree(file_fixture, ignore_errors=True)
        shutil.rmtree(source_snapshot, ignore_errors=True)
    overall = fatal is None and bool(results) and all(result["probe_pass"] for result in results)
    reproduced_hold = any(
        result.get("mode") == "hold" and result.get("probe_pass") is True
        and result.get("details", {}).get("baseline_hold_transition") is True
        for result in results
    )
    product_state = "not-established"
    if overall and args.phase == "baseline":
        product_state = "baseline-red-reproduced" if reproduced_hold else "baseline-observed"
    elif overall and args.phase == "candidate":
        product_state = "candidate-green"
    result_doc = {
        "timestamp": utc_now(),
        "phase": args.phase,
        "overall_probe_pass": overall,
        "product_state": product_state,
        "results": results,
        "fatal": fatal,
        "metadata": "metadata.json",
        "raw_output": "raw-output.jsonl",
        "raw_bidi": "bidi-raw.jsonl",
        "raw_server_network": "network-server.jsonl",
    }
    (output / "result.json").write_text(json.dumps(result_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    receipts.emit("probe-finished", overall_probe_pass=overall, product_state=result_doc["product_state"], cases=len(results))
    receipts.close()
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
