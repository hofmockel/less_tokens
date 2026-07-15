"""Unit tests for tools/strategy_table_docs.py — README strategy table renderer."""
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


docs = _load("strategy_table_docs", ".claude/tools/strategy_table_docs.py")


def test_render_round_trips_with_shipped_readme():
    """Smoke test: the rendered block matches what's actually checked in."""
    readme_text = docs.README.read_text(encoding="utf-8")
    assert docs.render() in readme_text


def test_check_passes_clean_against_shipped_readme():
    assert docs.update_docs(check=True) == 0


def test_replace_block_raises_without_markers():
    import pytest

    with pytest.raises(ValueError):
        docs._replace_block("no markers here", "replacement")
