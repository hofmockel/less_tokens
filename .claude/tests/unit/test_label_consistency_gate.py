"""Unit tests for tools/label_consistency_gate.py — measured-vs-asserted gate.

Pure function tests only: find_unbacked_claims takes README text + a registry
set and returns problems. No real README/registry content is asserted here
except the smoke test that the shipped README currently passes clean.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]

_spec = importlib.util.spec_from_file_location(
    "label_consistency_gate", REPO / ".claude" / "tools" / "label_consistency_gate.py"
)
gate = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(gate)

KNOWN = {"truncation", "compaction", "search"}


def _row(name: str, savings: str) -> str:
    return f"| **{name}** | some mechanism | {savings} | always on |\n"


def test_row_without_magnitude_is_ignored():
    text = _row("Read guards", "large-file Reads become small slices")
    assert gate.find_unbacked_claims(text, KNOWN) == []


def test_row_with_magnitude_and_registry_entry_passes():
    text = _row("Tool output truncation", "40-80% fewer tool-output tokens")
    assert gate.find_unbacked_claims(text, KNOWN) == []


def test_row_with_magnitude_and_no_registry_entry_but_marker_passes():
    text = _row(
        "Terse output mode", "30-60% fewer output tokens (not telemetry-backed)"
    )
    assert gate.find_unbacked_claims(text, KNOWN) == []


def test_row_with_magnitude_no_registry_no_marker_fails():
    text = _row("Terse output mode", "30-60% fewer output tokens")
    problems = gate.find_unbacked_claims(text, KNOWN)
    assert len(problems) == 1
    assert "Terse output mode" in problems[0]
    assert "no honesty marker" in problems[0]


def test_unmapped_strategy_name_fails_loudly():
    text = _row("Brand New Strategy", "99% fewer tokens")
    problems = gate.find_unbacked_claims(text, KNOWN)
    assert len(problems) == 1
    assert "not in README_STRATEGY_REGISTRY_MAP" in problems[0]


def test_multiplier_magnitude_is_detected():
    text = _row("Vector search + symbols", "5-10x fewer input tokens")
    # "x" not "×" should not match; only the literal × character does, matching
    # this repo's own README wording. Confirms the regex is precise, not loose.
    assert gate.MAGNITUDE.search("5-10x fewer input tokens") is None
    assert gate.MAGNITUDE.search("5–10× fewer input tokens") is not None


def test_registry_key_present_but_not_in_known_strategies_requires_marker():
    """A mapped key that isn't (yet) in the real registry should still fail
    without a marker — guards against the map drifting ahead of savings_log."""
    text = _row("Tool output truncation", "40-80% fewer tool-output tokens")
    assert gate.find_unbacked_claims(text, set()) != []


def test_shipped_readme_passes_clean():
    """Smoke test: the actual README.md in this repo has no unbacked claims."""
    readme_text = (REPO / "README.md").read_text(encoding="utf-8")
    known = gate._known_strategies()
    assert gate.find_unbacked_claims(readme_text, known) == []
