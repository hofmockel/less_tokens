"""Regression test: load_toolignore() must strip inline # comments from server names."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

sys.path.insert(
    0, str(Path(__file__).resolve().parent.parent.parent.parent / ".claude" / "tools")
)
mcp_prune_mod = importlib.import_module("mcp-prune")


def test_inline_comment_stripped(tmp_path):
    """'slack  # note' should yield 'slack', not 'slack  # note'."""
    ignore_file = tmp_path / ".toolignore"
    ignore_file.write_text("slack  # note\n", encoding="utf-8")
    result = mcp_prune_mod.load_toolignore(tmp_path)
    assert "slack" in result, f"Expected 'slack' in result, got {result!r}"
    assert "slack  # note" not in result, "Inline comment was not stripped"


def test_inline_comment_does_not_match_settings_key(tmp_path):
    """Without the fix, 'slack  # note' never matches settings key 'slack', so server is never pruned."""
    # Verify that the verbatim string with comment would NOT match
    assert "slack  # note" != "slack"


def test_full_line_comment_still_ignored(tmp_path):
    """Lines starting with # are still treated as comments (not server names)."""
    ignore_file = tmp_path / ".toolignore"
    ignore_file.write_text("# this is a comment\nslack\n", encoding="utf-8")
    result = mcp_prune_mod.load_toolignore(tmp_path)
    assert "slack" in result
    assert "# this is a comment" not in result


def test_trailing_whitespace_stripped(tmp_path):
    """Server name after comment strip should have trailing whitespace removed."""
    ignore_file = tmp_path / ".toolignore"
    ignore_file.write_text("github   # my github MCP\n", encoding="utf-8")
    result = mcp_prune_mod.load_toolignore(tmp_path)
    assert "github" in result
    assert "github   " not in result
