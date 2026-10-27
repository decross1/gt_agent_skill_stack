from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DESIGN_DIR = ROOT / "design"
QA_GATE_PATH = DESIGN_DIR / "scripts" / "qa_gate.py"
TRACE_SCRIPT_PATH = DESIGN_DIR / "scripts" / "record_agent_trace.py"
STAGED_PORTAL_HTML = Path(__file__).resolve().parents[1] / "oracle_harness/portal_view/index.html"

DESIGN_SKILLS = (
    "agent-viz",
    "lab-ui-build",
    "lab-ui-plan",
    "lab-ui-review",
    "trace-and-distill",
)


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_design_pack_skills_have_required_frontmatter():
    for skill in DESIGN_SKILLS:
        skill_md = ROOT / ".agents" / "skills" / skill / "SKILL.md"
        assert skill_md.is_file(), f"Missing {skill_md}"
        text = skill_md.read_text(encoding="utf-8")
        assert f"name: {skill}" in text
        assert "layer: B" in text
        assert "runtime-safe: false" in text
        assert "pack: design" in text


def test_design_knowledge_base_files_exist():
    for rel in (
        "product.md",
        "system.md",
        "reference-index.md",
        "harness-integration.md",
        "scripts/qa_gate.py",
        "scripts/linearize_context.py",
        "scripts/record_agent_trace.py",
        "evals/pilot_portal_8790_eval.json",
    ):
        assert (DESIGN_DIR / rel).is_file(), f"Missing design/{rel}"


def test_qa_gate_rejects_dl_and_unknown_slop_and_accepts_clean_bundle(tmp_path: Path):
    qa_gate = _load_module("qa_gate", QA_GATE_PATH)

    slop_html = tmp_path / "slop.html"
    slop_html.write_text(
        "<!doctype html><html><body><main>"
        + "".join(f"<dl><dt>k{i}</dt><dd>UNKNOWN</dd></dl>" for i in range(30))
        + "</main></body></html>",
        encoding="utf-8",
    )
    slop_report = qa_gate.inspect_html_bundle(slop_html)
    assert slop_report["passed"] is False
    violation_metrics = {v["metric"] for v in slop_report["violations"]}
    assert "unknown_badge_ratio" in violation_metrics
    assert "dl_term_count" in violation_metrics
    assert "missing_css_tokens" in violation_metrics

    qual = qa_gate.format_reharness_qualification(slop_report)
    assert qual["outcome_kind"] == "ui_qa_failure"
    assert any(p["field"] == "unknown_badge_ratio" for p in qual["falsified_when"])

    clean_css = (DESIGN_DIR / "system.md").read_text(encoding="utf-8")
    css_file = tmp_path / "styles.css"
    css_file.write_text(
        clean_css + "\nbody { overflow-x: hidden; font-variant-numeric: tabular-nums; }\n",
        encoding="utf-8",
    )
    clean_html = tmp_path / "clean.html"
    clean_html.write_text(
        '<!doctype html><html><head><link rel="stylesheet" href="/styles.css"></head>'
        '<body><a class="skip-link" href="#m">Skip</a><main id="m">'
        '<div role="tablist"><button role="tab">T1</button></div>'
        '<section role="tabpanel"><span class="status-pill">observed</span>'
        '<span class="status-pill">unmeasured</span><span class="status-pill">healthy</span>'
        '<p aria-live="polite">Ready</p></section></main></body></html>',
        encoding="utf-8",
    )
    clean_report = qa_gate.inspect_html_bundle(clean_html)
    assert clean_report["passed"] is True, clean_report["violations"]
    assert clean_report["metrics"]["unknown_badge_ratio"] == 0.0
    assert clean_report["metrics"]["dl_term_count"] == 0


def test_record_agent_trace_and_qualification_helpers():
    trace_mod = _load_module("record_agent_trace", TRACE_SCRIPT_PATH)
    entry = trace_mod.build_trace_entry(
        what="oracle_harness/portal_view/app.js",
        who="argon-reviewer",
        why="Add quota bullet bars and 1-hop ego highlighting",
        where="e61e26f",
        when="2026-10-27T05:30:00Z",
        skills_active=["agent-viz", "lab-ui-build"],
        qa_metrics={"unknown_badge_ratio": 0.0, "dl_term_count": 0},
    )
    assert entry["schema"] == "agent-trace/v1"
    assert len(entry["trace_sha256"]) == 64

    qual = trace_mod.build_qualification_row(
        qualification_id="qual:ui:001",
        prev_sha256="0" * 64,
        skill_path=".agents/skills/lab-ui-build/SKILL.md",
        skill_commit="e61e26f",
        skill_blob_sha="a" * 40,
        trigger_run_ref="portal_8790_pilot",
        applies_when=[{"field": "surface_kind", "op": "==", "value": "portal_8790"}],
        falsified_when=[{"field": "unknown_badge_ratio", "op": ">", "value": 0.05}],
        scope_narrowing="Render quota lane envelopes as bullet bars and distinguish unmeasured from 0.",
    )
    assert qual["schema"] == "reharness-qualification/v1"
    assert len(qual["row_sha256"]) == 64

    fb = trace_mod.build_feedback_entry(
        harvest_id="H-20261027-01",
        source="oracle_system",
        ref="e61e26f",
        skill="agent-viz",
        finding_class="confirmed",
        evidence="Bullet bars and 1-hop ego highlight improved scan speed.",
        date="2026-10-27",
    )
    assert fb["class"] == "confirmed"
    assert fb["skill"] == "agent-viz"


def test_portal_view_bundle_passes_qa_gate_and_features_if_present():
    if not STAGED_PORTAL_HTML.is_file():
        return
    qa_gate = _load_module("qa_gate", QA_GATE_PATH)
    report = qa_gate.inspect_html_bundle(STAGED_PORTAL_HTML)
    assert report["passed"] is True, report["violations"]
    assert report["metrics"]["unknown_badge_ratio"] == 0.0
    assert report["metrics"]["dl_term_count"] == 0
    assert report["metrics"]["external_cdn_count"] == 0

    app_js = (STAGED_PORTAL_HTML.parent / "app.js").read_text(encoding="utf-8")
    assert "bullet-track" in app_js
    assert "bullet-fill" in app_js
    assert "bullet-floor-tick" in app_js
    assert "highlightAtlasEgo" in app_js
    assert "panAtlas" in app_js


def test_install_sh_registers_all_four_harnesses_and_enforces_pi_firewall():
    install_sh = ROOT / "install.sh"
    if not install_sh.is_file():
        return
    proc = subprocess.run(
        ["bash", str(install_sh), "--list-targets"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    for target in ("claude-code", "codex", "argon", "pi"):
        assert target in proc.stdout
    assert "runtime-safe" in proc.stdout

    help_proc = subprocess.run(
        ["bash", str(install_sh), "--help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    for target in ("claude-code", "codex", "argon", "pi"):
        assert target in help_proc.stdout
