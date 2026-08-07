"""Regression test: mcp-prune._BASE must resolve to host project root, not less_tokens dir."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

_tools = Path(__file__).resolve().parent.parent.parent.parent / ".claude" / "tools"
sys.path.insert(0, str(_tools))
import db  # noqa: E402

mcp_prune = importlib.import_module("mcp-prune")


def test_find_base_uses_cwd_when_marker_present(tmp_path, monkeypatch):
    """When cwd contains .claude/tools/search_config.py, _find_base() returns cwd."""
    (tmp_path / ".claude" / "tools").mkdir(parents=True)
    (tmp_path / ".claude" / "tools" / "search_config.py").write_text(
        "", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    result = db._find_base()
    assert result == tmp_path.resolve()


def test_find_base_falls_back_to_file_ancestor(tmp_path, monkeypatch):
    """When cwd has no marker, _find_base() falls back to __file__-based ancestor."""
    monkeypatch.chdir(tmp_path)  # tmp_path has no .claude/tools/search_config.py
    result = db._find_base()
    expected = Path(db.__file__).resolve().parent.parent.parent
    assert result == expected


def test_base_module_constant_matches_find_base():
    """mcp-prune._BASE must equal db.BASE — both use the same _find_base logic."""
    assert mcp_prune._BASE == db.BASE
