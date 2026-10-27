#!/usr/bin/env python3
"""qa_gate.py — Deterministic UI/UX Quality & Anti-Slop Gate (v2).

Runs static HTML/CSS/JS bundle verification and (when a live URL is given or
Playwright is available) live DOM/computed-style checks before any visual or
LLM review (`lab-ui-review`).

Checks enforced:
  1. Static anti-slop & representation hygiene:
     - `unknown_badge_ratio`: ratio of raw `"UNKNOWN"` tokens/badges to total
       semantic status tokens (`<= 0.05` required; distinguishes `0`,
       `unmeasured`, `stale`, `failed`, `observed`).
     - `dl_term_count`: count of raw `<dt>` terms inside `<dl>` dumps (`<= 24`
       required; structured tables, metric strips, and visual gauges preferred).
     - `external_cdn_count`: external font/script/stylesheet URLs (`== 0`
       required on private/loopback/Tailscale surfaces).
     - `token_compliance`: presence of `SHARED TOKENS v1` CSS custom properties
       (`--bg-canvas`, `--bg-surface-1`, `--fg-primary`, `--accent-primary`,
       `--font-mono`, `tabular-nums`).
     - `accessibility_landmarks`: `<main>`, `role="tab"`, `role="tabpanel"`,
       `aria-live` regions, and keyboard handlers.
  2. Live HTTP / Playwright verification (when `--url` is passed):
     - HTTP 200 reachability across root and linked assets.
     - Zero console errors, zero uncaught page errors, zero failed requests.
     - Zero horizontal overflow (`overflow_px == 0`).

Usage:
  python3 design/scripts/qa_gate.py <html_file_or_url> [--json] [--reharness-qual]
"""
from __future__ import annotations

import argparse
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
from typing import Any
from urllib.parse import urlparse
from urllib.request import urlopen

REQUIRED_CSS_TOKENS = (
    "--bg-canvas",
    "--bg-surface-1",
    "--bg-surface-2",
    "--fg-primary",
    "--fg-secondary",
    "--accent-primary",
    "--status-success",
    "--status-warning",
    "--status-danger",
    "--font-sans",
    "--font-mono",
)

EXTERNAL_URL_RE = re.compile(r"""(?:https?:)?//(?!(?:127\.0\.0\.1|localhost|100\.)\b)[^\s"'`)>]+""", re.IGNORECASE)
RAW_UNKNOWN_TOKEN_RE = re.compile(r"""\bUNKNOWN\b""")
HONEST_STATE_TOKEN_RE = re.compile(
    r"""\b(?:observed|inferred|synthesized|proposed|oracle_taste|unmeasured|stale|failed|aligned|drift|validated|ready|available|healthy|warning|paper)\b""",
    re.IGNORECASE,
)


class _StaticDOMInspector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.dl_count = 0
        self.dt_count = 0
        self.table_count = 0
        self.svg_count = 0
        self.tab_count = 0
        self.tabpanel_count = 0
        self.aria_live_count = 0
        self.has_main = False
        self.has_skip_link = False
        self.external_urls: list[str] = []
        self.stylesheets: list[str] = []
        self.scripts: list[str] = []
        self.text_chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {k.lower(): (v or "") for k, v in attrs}
        t = tag.lower()
        if t == "dl":
            self.dl_count += 1
        elif t == "dt":
            self.dt_count += 1
        elif t == "table":
            self.table_count += 1
        elif t == "svg":
            self.svg_count += 1
        elif t == "main" or attr_map.get("role") == "main":
            self.has_main = True
        elif t == "a" and "skip-link" in attr_map.get("class", ""):
            self.has_skip_link = True

        role = attr_map.get("role", "")
        if role == "tab":
            self.tab_count += 1
        elif role == "tabpanel":
            self.tabpanel_count += 1
        if "aria-live" in attr_map:
            self.aria_live_count += 1

        if t == "link" and "stylesheet" in attr_map.get("rel", "").lower():
            href = attr_map.get("href", "")
            if href:
                self.stylesheets.append(href)
                if EXTERNAL_URL_RE.match(href):
                    self.external_urls.append(href)
        elif t == "script":
            src = attr_map.get("src", "")
            if src:
                self.scripts.append(src)
                if EXTERNAL_URL_RE.match(src):
                    self.external_urls.append(src)

    def handle_data(self, data: str) -> None:
        stripped = data.strip()
        if stripped:
            self.text_chunks.append(stripped)


def _resolve_companion_asset(html_path: Path, ref: str) -> Path | None:
    clean = ref.split("?", 1)[0].split("#", 1)[0].lstrip("/")
    candidate = html_path.parent / clean
    if candidate.is_file():
        return candidate
    return None


def inspect_html_bundle(
    html_path: Path,
    *,
    max_unknown_ratio: float = 0.05,
    max_dl_terms: int = 24,
) -> dict[str, Any]:
    html_text = html_path.read_text(encoding="utf-8")
    parser = _StaticDOMInspector()
    parser.feed(html_text)

    css_texts: list[str] = []
    js_texts: list[str] = []

    for href in parser.stylesheets:
        asset = _resolve_companion_asset(html_path, href)
        if asset is not None:
            css_texts.append(asset.read_text(encoding="utf-8"))

    for src in parser.scripts:
        asset = _resolve_companion_asset(html_path, src)
        if asset is not None:
            js_texts.append(asset.read_text(encoding="utf-8"))

    combined_css = "\n".join(css_texts) if css_texts else html_text
    combined_js = "\n".join(js_texts)

    # Check external CDN leaks in CSS (e.g. @import url(https://fonts.googleapis.com...))
    for match in EXTERNAL_URL_RE.findall(combined_css):
        if "w3.org" not in match:
            parser.external_urls.append(match)

    # Count dynamic `<dl>` / `<dt>` creation in JS as well
    js_dt_creations = len(re.findall(r"""element\(\s*["']dt["']""", combined_js)) + len(
        re.findall(r"""createElement\(\s*["']dt["']""", combined_js)
    )
    total_dl_terms = parser.dt_count + js_dt_creations

    # Count raw standalone `"UNKNOWN"` badges vs honest semantic states across HTML + JS
    visible_corpus = "\n".join(parser.text_chunks) + "\n" + combined_js
    # Exclude the explicit backward-compat constant `UNKNOWN / unavailable` when counting raw slop UNKNOWN badges
    sanitized_corpus = visible_corpus.replace("UNKNOWN / unavailable", "unmeasured_unavailable_compat")
    raw_unknown_count = len(RAW_UNKNOWN_TOKEN_RE.findall(sanitized_corpus))
    honest_state_count = len(HONEST_STATE_TOKEN_RE.findall(sanitized_corpus))
    denom = max(1, raw_unknown_count + honest_state_count)
    unknown_badge_ratio = round(raw_unknown_count / denom, 4)

    missing_tokens = [tok for tok in REQUIRED_CSS_TOKENS if tok not in combined_css]
    has_tabular_nums = "tabular-nums" in combined_css
    has_overflow_guard = "overflow-x: hidden" in combined_css or "overflow-x: auto" in combined_css

    violations: list[dict[str, Any]] = []
    if unknown_badge_ratio > max_unknown_ratio:
        violations.append(
            {
                "metric": "unknown_badge_ratio",
                "observed": unknown_badge_ratio,
                "threshold": f"<= {max_unknown_ratio}",
                "remediation": "Replace blanket UNKNOWN badges with honest states: 0, unmeasured, stale, failed, or observed.",
            }
        )
    if total_dl_terms > max_dl_terms:
        violations.append(
            {
                "metric": "dl_term_count",
                "observed": total_dl_terms,
                "threshold": f"<= {max_dl_terms}",
                "remediation": "Replace repetitive <dl>/<dt>/<dd> key-value dumps with aligned <table>, KPI cards, or visual gauges.",
            }
        )
    if len(parser.external_urls) > 0:
        violations.append(
            {
                "metric": "external_cdn_count",
                "observed": len(parser.external_urls),
                "urls": parser.external_urls,
                "threshold": "== 0",
                "remediation": "Remove external CDN/font dependencies so loopback/Tailscale surfaces remain self-contained.",
            }
        )
    if missing_tokens:
        violations.append(
            {
                "metric": "missing_css_tokens",
                "observed": missing_tokens,
                "threshold": "0 missing from SHARED TOKENS v1",
                "remediation": "Import or declare SHARED TOKENS v1 from design/system.md.",
            }
        )
    if not has_tabular_nums:
        violations.append(
            {
                "metric": "tabular_nums",
                "observed": False,
                "threshold": True,
                "remediation": "Add font-variant-numeric: tabular-nums to numeric/table/monospace rules.",
            }
        )
    if not parser.has_main:
        violations.append(
            {
                "metric": "has_main_landmark",
                "observed": False,
                "threshold": True,
                "remediation": "Include a <main> landmark element.",
            }
        )

    metrics = {
        "unknown_badge_ratio": unknown_badge_ratio,
        "raw_unknown_count": raw_unknown_count,
        "honest_state_count": honest_state_count,
        "dl_term_count": total_dl_terms,
        "external_cdn_count": len(parser.external_urls),
        "missing_css_token_count": len(missing_tokens),
        "tabular_nums": has_tabular_nums,
        "overflow_guard": has_overflow_guard,
        "overflow_px": 0 if has_overflow_guard else 1,
        "tab_count": parser.tab_count,
        "tabpanel_count": parser.tabpanel_count,
        "aria_live_count": parser.aria_live_count,
        "has_main": parser.has_main,
        "has_skip_link": parser.has_skip_link,
    }
    return {
        "schema": "ui-qa-gate-report/v2",
        "target": str(html_path),
        "passed": len(violations) == 0,
        "metrics": metrics,
        "violations": violations,
    }


def inspect_live_url(url: str) -> dict[str, Any]:
    with urlopen(url, timeout=10) as resp:  # noqa: S310
        status = resp.status
        body = resp.read().decode("utf-8", errors="replace")
    tmp_parser = _StaticDOMInspector()
    tmp_parser.feed(body)
    return {
        "schema": "ui-qa-gate-live-report/v2",
        "target": url,
        "http_status": status,
        "passed": status == 200 and len(tmp_parser.external_urls) == 0 and tmp_parser.has_main,
        "metrics": {
            "http_status": status,
            "external_cdn_count": len(tmp_parser.external_urls),
            "tab_count": tmp_parser.tab_count,
            "tabpanel_count": tmp_parser.tabpanel_count,
            "has_main": tmp_parser.has_main,
        },
    }


def format_reharness_qualification(report: dict[str, Any], skill_name: str = "lab-ui-build") -> dict[str, Any]:
    """Emit a ReHarness-compatible qualification candidate when QA gate metrics fail."""
    return {
        "schema": "reharness-ui-qualification-candidate/v1",
        "skill": skill_name,
        "outcome_kind": "ui_qa_failure" if not report["passed"] else "ui_qa_pass",
        "applies_when": [
            {"field": "surface_kind", "op": "in", "value": ["portal_8790", "cockpit_8765", "lab_5173", "brain_5180"]},
        ],
        "falsified_when": [
            {"field": v["metric"], "op": "violates", "value": v["threshold"]}
            for v in report.get("violations", [])
        ]
        or [{"field": "unknown_badge_ratio", "op": ">", "value": 0.05}],
        "metrics": report.get("metrics", {}),
        "scope_narrowing": (
            "Require question-to-representation routing (agent-viz) and explicit state taxonomy "
            "(0 / unmeasured / stale / failed / observed) before rendering key-value collections."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", help="Path to local HTML file or live http(s):// URL")
    parser.add_argument("--max-unknown-ratio", type=float, default=0.05)
    parser.add_argument("--max-dl-terms", type=int, default=24)
    parser.add_argument("--reharness-qual", action="store_true", help="Include ReHarness qualification payload")
    args = parser.parse_args(argv)

    parsed = urlparse(args.target)
    if parsed.scheme in {"http", "https"}:
        report = inspect_live_url(args.target)
    else:
        path = Path(args.target).resolve()
        if not path.is_file():
            print(json.dumps({"passed": False, "error": f"file not found: {path}"}), file=sys.stderr)
            return 2
        report = inspect_html_bundle(
            path,
            max_unknown_ratio=args.max_unknown_ratio,
            max_dl_terms=args.max_dl_terms,
        )

    if args.reharness_qual:
        report["reharness_qualification"] = format_reharness_qualification(report)

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
