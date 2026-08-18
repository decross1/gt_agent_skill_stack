"""Static guardrails for the browser-verified narrow brain views."""
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
VIEW = REPO / "memory" / "brain" / "view"


def test_graph_mobile_header_panel_and_demo_are_bounded():
    graph = (VIEW / "graph.html").read_text()
    shared = (VIEW / "ui.js").read_text()
    assert "header .stepper,header .asof,header .xnav{display:none}" in graph
    assert "max-width:100vw;box-sizing:border-box" in graph
    assert "if (window.innerWidth >= 760) inst.demoCard()" in graph
    assert "max-width:100vw;box-sizing:border-box" in shared


def test_review_mobile_header_and_detail_are_bounded():
    review = (VIEW / "proposal_review.html").read_text()
    assert ".brand .sub, header .gerr { display:none; }" in review
    assert "nav.views a { padding-left:8px; padding-right:8px; }" in review
    assert "#detail { padding:14px 10px 48px; }" in review
