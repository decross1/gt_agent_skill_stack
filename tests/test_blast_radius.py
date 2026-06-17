#!/usr/bin/env python3
"""Tests for scripts/blast_radius.py — the deterministic blast-radius classifier.

blast_radius(first) reads only the proposal's first row (a dict with target_type
and target) and decides "low" (localized, auto-promotable brain content) or
"high" (governance reach → human). It is pure stdlib: the only side input is a
grep of .agents/skills/<target>/SKILL.md for `runtime-safe: true`, against the
REAL repo skills dir — so these assertions ride the framework's own skills.

Conservative-default contract under test: anything the classifier cannot
positively place as localized is "high", so a novel proposal shape can never be
auto-promoted by accident.
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import blast_radius as br  # noqa: E402


def test_skill_target_type_is_high():
    # target_type "skill" is always governance reach.
    assert br.blast_radius({"target_type": "skill", "target": "validate"}) == "high"


def test_rule_target_type_is_high():
    assert br.blast_radius({"target_type": "rule", "target": "no-coerce"}) == "high"


def test_load_bearing_root_targets_are_high():
    # A non-governance target_type, but the target names a load-bearing root file.
    for target in ("rules.md", "DECISIONS.md", "install.sh"):
        assert br.blast_radius({"target_type": "brain-page", "target": target}) == "high", target


def test_runtime_safe_core_skill_as_target_is_high():
    # `fallback` is one of the 6 runtime-safe core skills (BOUNDARY.md). Even with
    # a localized target_type, naming it as the target reaches the firewall core.
    assert br._is_runtime_safe_core("fallback") is True
    assert br.blast_radius({"target_type": "edge", "target": "fallback"}) == "high"


def test_localized_target_types_are_low():
    for ttype in ("brain-page", "edge"):
        assert br.blast_radius({"target_type": ttype, "target": "some-page"}) == "low", ttype


def test_unknown_target_type_is_high_conservative_default():
    # A novel / unrecognized shape must never auto-promote.
    assert br.blast_radius({"target_type": "newfangled", "target": "x"}) == "high"


def test_empty_target_type_is_high_conservative_default():
    assert br.blast_radius({"target_type": "", "target": ""}) == "high"
    assert br.blast_radius({}) == "high"
