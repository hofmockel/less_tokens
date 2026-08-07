"""Bug: _resolve() skips rglob fallback when path contains '/'.

`tools/search.py` resolves to `BASE/tools/search.py` (missing); the rglob
fallback that would find `.claude/tools/search.py` is gated on '/' absence.
Fix: remove the '/' guard so rglob is always tried as fallback.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).parent.parent.parent / "tools"
sys.path.insert(0, str(TOOLS))

import claudemd_audit  # noqa: E402


def test_resolve_partial_path_with_slash(tmp_path):
    """`tools/search.py` must resolve even when BASE/tools/search.py doesn't exist."""
    # Set up a tree: tmp_path/.claude/tools/search.py
    nested = tmp_path / ".claude" / "tools"
    nested.mkdir(parents=True)
    target = nested / "search.py"
    target.write_text("# search")

    with patch.object(claudemd_audit, "BASE", tmp_path):
        result = claudemd_audit._resolve("tools/search.py")

    assert result is not None, (
        "_resolve() returned None for a partial path with '/'; "
        "rglob fallback was incorrectly skipped"
    )
    assert result == target


def test_resolve_bare_filename_still_works(tmp_path):
    """Bare filenames (no '/') must still resolve via rglob (regression guard)."""
    nested = tmp_path / "sub" / "dir"
    nested.mkdir(parents=True)
    target = nested / "myfile.py"
    target.write_text("# x")

    with patch.object(claudemd_audit, "BASE", tmp_path):
        result = claudemd_audit._resolve("myfile.py")

    assert result == target


def test_resolve_direct_path_still_works(tmp_path):
    """Direct BASE-relative paths must still resolve (regression guard)."""
    target = tmp_path / "CLAUDE.md"
    target.write_text("# hi")

    with patch.object(claudemd_audit, "BASE", tmp_path):
        result = claudemd_audit._resolve("CLAUDE.md")

    assert result == target


def test_resolve_missing_returns_none(tmp_path):
    """Non-existent paths must return None (regression guard)."""
    with patch.object(claudemd_audit, "BASE", tmp_path):
        result = claudemd_audit._resolve("tools/no_such_file.py")

    assert result is None
