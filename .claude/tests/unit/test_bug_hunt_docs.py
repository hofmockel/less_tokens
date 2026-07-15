"""Unit tests for tools/bug_hunt_docs.py — bug-hunt-protocol.md block renderer."""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]


def _load(name: str, rel_path: str):
    spec = importlib.util.spec_from_file_location(name, REPO / rel_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


docs = _load("bug_hunt_docs", ".claude/tools/bug_hunt_docs.py")


def test_check_passes_clean_against_shipped_protocol():
    assert docs.update_docs(check=True) == 0


def test_all_rendered_blocks_present_in_shipped_protocol():
    protocol_text = docs.PROTOCOL.read_text(encoding="utf-8")
    for name, render in docs.RENDERERS.items():
        assert render() in protocol_text, f"{name} block out of sync"


def test_replace_block_raises_without_markers():
    import pytest

    with pytest.raises(ValueError):
        docs._replace_block("no markers here", "severity-rubric", "replacement")


def test_target_files_render_matches_registry_count():
    rendered = docs._render_target_files()
    assert f"({len(docs.TARGET_FILES)} files)" in rendered
