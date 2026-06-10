"""Regression test: mcp-prune._find_base() must resolve to host project root, not less_tokens dir."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / ".claude" / "tools"))
mcp_prune = importlib.import_module("mcp-prune")


def test_find_base_uses_cwd_when_marker_present(tmp_path, monkeypatch):
    """When cwd contains .claude/tools/search_config.py, _find_base() returns cwd."""
    (tmp_path / ".claude" / "tools").mkdir(parents=True)
    (tmp_path / ".claude" / "tools" / "search_config.py").write_text("", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    result = mcp_prune._find_base()
    assert result == tmp_path.resolve()


def test_find_base_falls_back_to_file_ancestor(tmp_path, monkeypatch):
    """When cwd has no marker, _find_base() falls back to __file__-based ancestor."""
    monkeypatch.chdir(tmp_path)  # tmp_path has no .claude/tools/search_config.py
    result = mcp_prune._find_base()
    # Should be 3 parents above mcp-prune.py — not tmp_path
    expected = Path(mcp_prune.__file__).resolve().parent.parent.parent
    assert result == expected


def test_base_module_constant_matches_find_base():
    """_BASE module constant must equal _find_base() called at the same cwd."""
    assert mcp_prune._BASE == mcp_prune._find_base()
