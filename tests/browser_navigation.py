#!/usr/bin/env python3
"""Small, dependency-free W3C navigation boundary for Firefox.

The boundary deliberately keeps document readiness, element interaction, and
application-specific state observation separate.  Callers provide short state
scripts and predicates; returned objects are capped before they reach receipts.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import http.server
import json
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
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


W3C_ELEMENT_KEY = "element-6066-11e4-a52e-4f735466cecf"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_identity(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {"path": str(path.resolve()), "bytes": len(data), "sha256": sha256_bytes(data)}


def compact(value: Any, limit: int = 800) -> str:
    try:
        rendered = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError):
        rendered = repr(value)
    return rendered if len(rendered) <= limit else rendered[:limit] + "…"


class NavigationTimeout(TimeoutError):
    """A bounded browser wait expired without meeting its predicate."""


class WebDriverCommandError(RuntimeError):
    """A W3C command returned an error response."""

    def __init__(self, method: str, path: str, status: int, payload: Any):
        value = payload.get("value", payload) if isinstance(payload, dict) else payload
        self.error = value.get("error", "unknown error") if isinstance(value, dict) else "unknown error"
        self.detail = value.get("message", compact(value)) if isinstance(value, dict) else compact(value)
        self.method, self.path, self.status, self.payload = method, path, status, payload
        super().__init__(f"WebDriver {method} {path} returned {status} {self.error}: {self.detail}")


def allocate_loopback_ports(count: int) -> list[int]:
    """Reserve distinct ephemeral loopback ports together, then release them."""
    sockets: list[socket.socket] = []
    try:
        for _ in range(count):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(("127.0.0.1", 0))
            sockets.append(sock)
        ports = [int(sock.getsockname()[1]) for sock in sockets]
        if len(set(ports)) != count:
            raise RuntimeError("ephemeral port allocation returned duplicates")
        return ports
    finally:
        for sock in sockets:
            sock.close()


def port_is_closed(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.15)
        return sock.connect_ex(("127.0.0.1", port)) != 0


def path_is_within(path: Path, root: Path) -> bool:
    return path.resolve(strict=False).is_relative_to(root.resolve(strict=False))


def wait_until(
    read: Callable[[], Any],
    predicate: Callable[[Any], bool],
    *,
    timeout: float,
    interval: float = 0.05,
    description: str = "condition",
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> Any:
    """Poll through transient values while propagating unrelated exceptions."""
    deadline = clock() + timeout
    last: Any = None
    while True:
        last = read()
        if predicate(last):
            return last
        if clock() >= deadline:
            raise NavigationTimeout(f"{description} did not become ready; last={compact(last)}")
        sleep(min(interval, max(0.0, deadline - clock())))


class WebDriverClient:
    """Minimal W3C HTTP client with command metadata and bounded results."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.commands: list[dict[str, Any]] = []

    def command(self, method: str, path: str, payload: Any = None, *, timeout: float = 10) -> Any:
        started = time.monotonic()
        body = None if payload is None else json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers = {"Content-Type": "application/json; charset=utf-8"} if body is not None else {}
        request = urllib.request.Request(self.base_url + path, data=body, headers=headers, method=method)
        status = 0
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                status, raw = response.status, response.read()
        except urllib.error.HTTPError as error:
            status, raw = error.code, error.read()
        except Exception as error:
            self.commands.append({
                "method": method, "path": path, "status": 0,
                "duration_ms": round((time.monotonic() - started) * 1000),
                "error": f"{type(error).__name__}: {error}",
            })
            raise
        invalid_json = False
        try:
            parsed = json.loads(raw) if raw else None
        except json.JSONDecodeError as error:
            parsed = {"value": {"error": "invalid response", "message": str(error)}}
            invalid_json = True
        row = {
            "method": method, "path": path, "status": status,
            "duration_ms": round((time.monotonic() - started) * 1000),
        }
        if status >= 400 or invalid_json:
            row["error"] = compact(parsed)
            self.commands.append(row)
            raise WebDriverCommandError(method, path, status, parsed)
        self.commands.append(row)
        return parsed.get("value") if isinstance(parsed, dict) and "value" in parsed else parsed


@dataclass
class BrowserCleanup:
    session_deleted: bool = False
    driver_exit_code: int | None = None
    driver_killed: bool = False
    profile_within_root: bool = False
    profile_removed: bool = False
    profile_root_within_parent: bool = False
    profile_root_removed: bool = False
    ports_closed: dict[str, bool] | None = None
    errors: list[str] | None = None


def cleanup_is_qualified(cleanup: BrowserCleanup) -> bool:
    return (
        cleanup.session_deleted
        and cleanup.profile_within_root
        and cleanup.profile_removed
        and cleanup.profile_root_within_parent
        and cleanup.profile_root_removed
        and bool(cleanup.ports_closed)
        and all(cleanup.ports_closed.values())
        and not cleanup.errors
    )


class FirefoxNavigation:
    """Own one isolated Firefox/geckodriver session and only its resources."""

    def __init__(
        self,
        *,
        artifact_root: Path,
        profile_parent: Path,
        geckodriver: str | None = None,
        firefox: str | None = None,
        page_load_strategy: str = "normal",
        window: tuple[int, int] = (1280, 900),
        profile_prefix: str = "browser-navigation-",
    ):
        self.artifact_root = artifact_root.resolve()
        self.profile_parent = profile_parent.resolve()
        self.geckodriver = geckodriver or shutil.which("geckodriver") or ""
        self.firefox = firefox or shutil.which("firefox") or ""
        self.page_load_strategy = page_load_strategy
        self.window = window
        self.profile_prefix = profile_prefix
        self.ports: dict[str, int] = {}
        self.driver_argv: list[str] = []
        self.driver_process: subprocess.Popen[str] | None = None
        self.driver_log = None
        self.client: WebDriverClient | None = None
        self.session_id = ""
        self.capabilities: dict[str, Any] = {}
        self.profile_root: Path | None = None
        self.profile: Path | None = None
        self.cleanup = BrowserCleanup(errors=[])
        self.started_at = ""

    def __enter__(self) -> "FirefoxNavigation":
        return self.start()

    def __exit__(self, _kind, _error, _traceback) -> None:
        self.close()

    def start(self) -> "FirefoxNavigation":
        if self.driver_process is not None:
            raise RuntimeError("FirefoxNavigation instances are single-use")
        if not self.geckodriver or not Path(self.geckodriver).exists():
            raise FileNotFoundError("geckodriver is not installed")
        if not self.firefox or not Path(self.firefox).exists():
            raise FileNotFoundError("Firefox is not installed")
        if not self.profile_parent.is_dir():
            raise FileNotFoundError(f"profile parent does not exist: {self.profile_parent}")
        self.artifact_root.mkdir(parents=True, exist_ok=True)
        self.started_at = utc_now()
        driver_port, marionette_port, bidi_port = allocate_loopback_ports(3)
        self.ports = {"webdriver": driver_port, "marionette": marionette_port, "bidi": bidi_port}
        if 9222 in self.ports.values():
            raise RuntimeError("isolated port allocation unexpectedly selected the default BiDi port")
        self.profile_root = Path(tempfile.mkdtemp(prefix=self.profile_prefix, dir=self.profile_parent))
        self.driver_argv = [
            self.geckodriver,
            "--host", "127.0.0.1",
            "--port", str(driver_port),
            "--marionette-port", str(marionette_port),
            "--websocket-port", str(bidi_port),
            "--profile-root", str(self.profile_root),
        ]
        self.driver_log = (self.artifact_root / "geckodriver.log").open("w", encoding="utf-8")
        self.driver_process = subprocess.Popen(
            self.driver_argv,
            stdout=self.driver_log,
            stderr=subprocess.STDOUT,
            text=True,
        )
        self.client = WebDriverClient(f"http://127.0.0.1:{driver_port}")
        try:
            wait_until(
                self._read_driver_status,
                lambda value: isinstance(value, dict) and value.get("ready") is True,
                timeout=12,
                interval=0.1,
                description="geckodriver status",
            )
            result = self.client.command("POST", "/session", {
                "capabilities": {"alwaysMatch": {
                    "browserName": "firefox",
                    "acceptInsecureCerts": False,
                    "pageLoadStrategy": self.page_load_strategy,
                    "webSocketUrl": False,
                    "moz:firefoxOptions": {"args": ["-headless"]},
                }}
            }, timeout=35)
            if not isinstance(result, dict) or not isinstance(result.get("sessionId"), str):
                raise RuntimeError(f"invalid new-session response: {compact(result)}")
            self.session_id = result["sessionId"]
            self.capabilities = result.get("capabilities", {})
            profile = self.capabilities.get("moz:profile")
            self.profile = Path(profile) if isinstance(profile, str) else None
            self.client.command("POST", self._path("/window/rect"), {
                "width": self.window[0], "height": self.window[1]
            })
            self.client.command("POST", self._path("/timeouts"), {
                "implicit": 0, "pageLoad": 15000, "script": 5000
            })
            return self
        except Exception:
            self.close()
            raise

    def _read_driver_status(self) -> Any:
        assert self.client is not None and self.driver_process is not None
        try:
            return self.client.command("GET", "/status", timeout=1)
        except urllib.error.URLError as error:
            if isinstance(error.reason, ConnectionRefusedError) and self.driver_process.poll() is None:
                return None
            raise

    def _path(self, suffix: str) -> str:
        if not self.session_id:
            raise RuntimeError("browser session is not open")
        return f"/session/{self.session_id}{suffix}"

    def navigate(self, url: str) -> None:
        assert self.client is not None
        self.client.command("POST", self._path("/url"), {"url": url}, timeout=20)

    def execute_small(self, script: str, args: list[Any] | None = None, *, max_bytes: int = 16384) -> Any:
        assert self.client is not None
        value = self.client.command("POST", self._path("/execute/sync"), {
            "script": script, "args": args or []
        }, timeout=8)
        encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if len(encoded) > max_bytes:
            raise ValueError(f"browser state exceeded {max_bytes} bytes ({len(encoded)} bytes returned)")
        return value

    def wait_for_document(self, *, timeout: float = 10) -> dict[str, Any]:
        script = "return {readyState:document.readyState,url:String(location.href),title:document.title};"
        return wait_until(
            lambda: self.execute_small(script, max_bytes=4096),
            lambda value: isinstance(value, dict) and value.get("readyState") == "complete",
            timeout=timeout,
            description="document complete",
        )

    def wait_for_state(
        self,
        script: str,
        predicate: Callable[[dict[str, Any]], bool],
        *,
        timeout: float,
        description: str,
        max_bytes: int = 16384,
    ) -> dict[str, Any]:
        return wait_until(
            lambda: self.execute_small(script, max_bytes=max_bytes),
            lambda value: isinstance(value, dict) and predicate(value),
            timeout=timeout,
            description=description,
        )

    def find_element(self, selector: str) -> str:
        assert self.client is not None
        value = self.client.command("POST", self._path("/element"), {
            "using": "css selector", "value": selector
        })
        if not isinstance(value, dict) or not isinstance(value.get(W3C_ELEMENT_KEY), str):
            raise RuntimeError(f"invalid element response for {selector!r}: {compact(value)}")
        return value[W3C_ELEMENT_KEY]

    def element_is_displayed(self, element_id: str) -> bool:
        assert self.client is not None
        return self.client.command("GET", self._path(f"/element/{element_id}/displayed")) is True

    def wait_for_visible_element(self, selector: str, *, timeout: float = 8) -> str:
        def read() -> str | None:
            try:
                element_id = self.find_element(selector)
                return element_id if self.element_is_displayed(element_id) else None
            except WebDriverCommandError as error:
                if error.error in {"no such element", "stale element reference"}:
                    return None
                raise
        return wait_until(read, lambda value: isinstance(value, str), timeout=timeout,
                          description=f"visible element {selector!r}")

    def click_element(self, element_id: str) -> None:
        assert self.client is not None
        self.client.command("POST", self._path(f"/element/{element_id}/click"), {})

    def click_visible(self, selector: str, *, timeout: float = 8) -> str:
        deadline = time.monotonic() + timeout
        while True:
            element_id = self.wait_for_visible_element(selector, timeout=max(0.1, deadline - time.monotonic()))
            try:
                self.click_element(element_id)
                return element_id
            except WebDriverCommandError as error:
                if error.error != "stale element reference" or time.monotonic() >= deadline:
                    raise

    def screenshot(self, path: Path) -> dict[str, Any]:
        assert self.client is not None
        encoded = self.client.command("GET", self._path("/screenshot"), timeout=10)
        if not isinstance(encoded, str):
            raise RuntimeError("WebDriver screenshot response was not base64 text")
        data = base64.b64decode(encoded, validate=True)
        path.write_bytes(data)
        return file_identity(path)

    def close(self) -> BrowserCleanup:
        errors = self.cleanup.errors if self.cleanup.errors is not None else []
        if self.client is not None and self.session_id:
            try:
                self.client.command("DELETE", self._path(""), timeout=12)
                self.cleanup.session_deleted = True
            except Exception as error:
                errors.append(f"session delete: {type(error).__name__}: {error}")
            self.session_id = ""
        process = self.driver_process
        if process is not None:
            try:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
                        self.cleanup.driver_killed = True
                self.cleanup.driver_exit_code = process.returncode
            except Exception as error:
                errors.append(f"driver cleanup: {type(error).__name__}: {error}")
        if self.driver_log is not None and not self.driver_log.closed:
            try:
                self.driver_log.close()
            except Exception as error:
                errors.append(f"driver log close: {type(error).__name__}: {error}")
        if self.profile_root is not None:
            self.cleanup.profile_root_within_parent = path_is_within(self.profile_root, self.profile_parent)
        if self.profile is not None and self.profile_root is not None:
            self.cleanup.profile_within_root = path_is_within(self.profile, self.profile_root)
        if self.profile is None:
            errors.append("browser capabilities did not report moz:profile")
        elif not self.cleanup.profile_within_root:
            errors.append(f"refused to remove reported profile outside owned root: {self.profile}")
        if self.profile_root is not None and self.cleanup.profile_root_within_parent:
            try:
                if self.profile_root.exists():
                    shutil.rmtree(self.profile_root)
            except Exception as error:
                errors.append(f"profile root cleanup: {type(error).__name__}: {error}")
        elif self.profile_root is not None:
            errors.append(f"refused to remove profile root outside configured parent: {self.profile_root}")
        self.cleanup.profile_root_removed = self.profile_root is not None and not self.profile_root.exists()
        self.cleanup.profile_removed = (
            self.profile is not None and self.cleanup.profile_within_root and not self.profile.exists()
        )
        closed: dict[str, bool] = {}
        for name, port in self.ports.items():
            try:
                wait_until(lambda p=port: port_is_closed(p), bool, timeout=3,
                           interval=0.05, description=f"closed {name} port")
                closed[name] = True
            except NavigationTimeout:
                closed[name] = False
            except Exception as error:
                closed[name] = False
                errors.append(f"{name} port cleanup check: {type(error).__name__}: {error}")
        self.cleanup.ports_closed = closed
        self.cleanup.errors = errors
        return self.cleanup

    def identity(self) -> dict[str, Any]:
        def version(argv: list[str]) -> str:
            result = subprocess.run(argv, capture_output=True, text=True, timeout=10)
            return (result.stdout + result.stderr).strip()
        return {
            "started_at": self.started_at,
            "geckodriver": {"path": str(Path(self.geckodriver).resolve()), "version": version([self.geckodriver, "--version"])},
            "firefox": {"path": str(Path(self.firefox).resolve()), "version": version([self.firefox, "--version"])},
            "driver_pid": self.driver_process.pid if self.driver_process else None,
            "driver_argv": self.driver_argv,
            "ports": self.ports,
            "profile_root": str(self.profile_root) if self.profile_root else None,
            "profile": str(self.profile) if self.profile else None,
            "capabilities": self.capabilities,
        }


SMOKE_PAGE = b"""<!doctype html><html><head><meta charset=utf-8><title>Navigation smoke</title></head>
<body><main><h1>Normal navigation</h1><button id=choose type=button>Choose</button>
<output id=result>idle</output></main><script>
document.getElementById('choose').addEventListener('click',()=>{
 const out=document.getElementById('result');
 document.body.dataset.clicked='yes';out.dataset.count=String(Number(out.dataset.count||0)+1);out.textContent='chosen';
});
</script></body></html>"""


class _SmokeServer(http.server.ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False


def run_smoke(output: Path, profile_parent: Path, *, argv: list[str]) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=False)
    requests: list[dict[str, Any]] = []
    lock = threading.Lock()

    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_args: Any) -> None:
            return

        def do_GET(self) -> None:  # noqa: N802
            data, status = (SMOKE_PAGE, 200) if self.path.split("?", 1)[0] == "/" else (b"not found\n", 404)
            with lock:
                requests.append({"at": utc_now(), "method": "GET", "path": self.path,
                                 "status": status, "bytes": len(data), "sha256": sha256_bytes(data)})
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(data)

    server = _SmokeServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, name="browser-navigation-smoke", daemon=True)
    receipt: dict[str, Any] = {
        "started_at": utc_now(), "status": "running", "argv": argv,
        "program": file_identity(Path(__file__)), "page": {"bytes": len(SMOKE_PAGE), "sha256": sha256_bytes(SMOKE_PAGE)},
        "actions": [], "checks": [], "captures": [], "manual_render_or_handler_calls": 0,
    }
    browser = FirefoxNavigation(
        artifact_root=output, profile_parent=profile_parent,
        page_load_strategy="normal", profile_prefix="as041-normal-navigation-",
    )
    state_script = "return {clicked:document.body.dataset.clicked||'',text:document.getElementById('result')?.textContent||'',count:document.getElementById('result')?.dataset.count||''};"
    try:
        thread.start()
        browser.start()
        receipt["browser"] = browser.identity()
        url = f"http://127.0.0.1:{server.server_port}/"
        browser.navigate(url)
        receipt["actions"].append({"at": utc_now(), "kind": "W3C navigation", "url": url})
        document = browser.wait_for_document(timeout=10)
        receipt["checks"].append({"criterion": "ordinary document readiness", "verdict": "pass", "observed": document})
        element_id = browser.wait_for_visible_element("#choose")
        receipt["checks"].append({"criterion": "real button is displayed", "verdict": "pass", "observed": {"selector": "#choose", "element": element_id}})
        receipt["captures"].append({"name": "before-click", **browser.screenshot(output / "before-click.png")})
        browser.click_element(element_id)
        receipt["actions"].append({"at": utc_now(), "kind": "W3C element click", "selector": "#choose", "element": element_id})
        after = browser.wait_for_state(
            state_script, lambda value: value == {"clicked": "yes", "text": "chosen", "count": "1"},
            timeout=5, description="click result",
        )
        time.sleep(0.2)
        stable = browser.execute_small(state_script, max_bytes=1024)
        if stable != after:
            raise AssertionError(f"post-click state was not stable: {compact(after)} -> {compact(stable)}")
        receipt["checks"].append({"criterion": "single click produces stable small state", "verdict": "pass", "observed": stable})
        receipt["captures"].append({"name": "after-click", **browser.screenshot(output / "after-click.png")})
        receipt["status"] = "passed"
    except Exception as error:
        receipt.update(status="failed", error=f"{type(error).__name__}: {error}", traceback=traceback.format_exc())
    finally:
        cleanup_errors: list[str] = []
        try:
            browser.close()
        except Exception as error:
            cleanup_errors.append(f"browser close: {type(error).__name__}: {error}")
        try:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        except Exception as error:
            cleanup_errors.append(f"fixture close: {type(error).__name__}: {error}")
        browser_identity = receipt.get("browser", {})
        if not browser_identity:
            try:
                browser_identity = browser.identity()
            except Exception as error:
                cleanup_errors.append(f"browser identity: {type(error).__name__}: {error}")
                browser_identity = {"driver_argv": browser.driver_argv, "ports": browser.ports,
                                    "profile_root": str(browser.profile_root), "profile": str(browser.profile)}
        receipt["browser"] = {**browser_identity,
                              "commands": browser.client.commands if browser.client else [],
                              "cleanup": vars(browser.cleanup)}
        fixture_closed = port_is_closed(server.server_port) and not thread.is_alive()
        receipt["fixture"] = {"port": server.server_port, "port_closed": port_is_closed(server.server_port),
                              "thread_stopped": not thread.is_alive(), "requests": requests}
        cleanup_ok = cleanup_is_qualified(browser.cleanup) and fixture_closed and not cleanup_errors
        receipt["checks"].append({"criterion": "owned browser and fixture cleanup", "verdict": "pass" if cleanup_ok else "fail",
                                  "observed": {"browser": vars(browser.cleanup), "fixture_closed": fixture_closed,
                                               "errors": cleanup_errors}})
        if not cleanup_ok:
            receipt["status"] = "failed"
            receipt.setdefault("error", "cleanup qualification failed")
        elif receipt["status"] == "running":
            receipt["status"] = "failed"
            receipt.setdefault("error", "browser run ended without a result")
        receipt["finished_at"] = utc_now()
        (output / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(argv) if argv is not None else sys.argv[1:]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true", help="run a finite ordinary-page Firefox click smoke")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile-parent", type=Path, required=True,
                        help="existing directory visible to the installed Firefox package")
    args = parser.parse_args(argv)
    if not args.smoke:
        parser.error("--smoke is required when running this module directly")
    receipt = run_smoke(args.output.resolve(), args.profile_parent.resolve(),
                        argv=[sys.executable, str(Path(__file__).resolve()), *raw_argv])
    print(json.dumps({"status": receipt["status"], "checks": len(receipt["checks"]), "output": str(args.output.resolve())}))
    return 0 if receipt["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
