"""Tests for the HP1 conformance/savings workload matrix."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(REPO))

from agents.common.conformance.workloads import WORKLOADS  # noqa: E402

_SPEC = importlib.util.spec_from_file_location(
    "conformance_matrix",
    REPO / ".claude" / "tools" / "conformance_matrix.py",
)
assert _SPEC and _SPEC.loader
conformance_matrix = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(conformance_matrix)

REQUIRED_FIELDS = ("code_present", "configured", "event_fired", "action_enforced", "basis", "fixture")


def _matrix() -> dict:
    return json.loads(conformance_matrix.MATRIX.read_text(encoding="utf-8"))


def test_every_workload_has_an_entry_per_supported_cell():
    matrix = _matrix()
    for workload in WORKLOADS:
        for agent, release in conformance_matrix.CELLS:
            key = f"{workload.slug}:{agent}:{release}"
            assert key in matrix, f"missing matrix entry for {key}"


def test_measured_entries_carry_all_required_fields():
    matrix = _matrix()
    for key, entry in matrix.items():
        if entry.get("status") == "not_yet_measured":
            assert set(entry) == {"status"}, f"{key} has status plus stray fields"
            continue
        for field in REQUIRED_FIELDS:
            assert field in entry, f"{key} missing required field {field}"


def test_no_entry_is_a_guessed_number():
    matrix = _matrix()
    for key, entry in matrix.items():
        if entry.get("status") == "not_yet_measured":
            continue
        assert entry["basis"] == "measured", f"{key} basis is not 'measured': {entry['basis']!r}"


def test_render_contains_markers_and_every_workload():
    block = conformance_matrix.render()
    assert block.startswith(conformance_matrix.BEGIN)
    assert block.endswith(conformance_matrix.END)
    for workload in WORKLOADS:
        assert f"`{workload.slug}:claude:2026-07-21`" in block


def test_conformance_matrix_docs_are_current():
    block = conformance_matrix.render()
    for path in conformance_matrix.DOCS:
        text = path.read_text(encoding="utf-8")
        assert conformance_matrix._replace_block(text, block) == text


def test_check_mode_detects_drift(tmp_path, monkeypatch):
    stale = REPO / "README.md"
    text = stale.read_text(encoding="utf-8")
    drifted = text.replace(conformance_matrix.BEGIN, conformance_matrix.BEGIN + "\nSTALE", 1)
    tmp_readme = tmp_path / "README.md"
    tmp_readme.write_text(drifted, encoding="utf-8")
    monkeypatch.setattr(conformance_matrix, "REPO", tmp_path)
    monkeypatch.setattr(conformance_matrix, "DOCS", (tmp_readme,))
    assert conformance_matrix.update_docs(check=True) == 1
