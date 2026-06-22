"""Regression test: _remove_gitignore_block must not leave an orphan blank line
after the managed block is removed."""
from __future__ import annotations

from pathlib import Path

import install

_START = install._GI_START
_END = install._GI_END


def _make_gi(tmp_path: Path, content: str) -> Path:
    gi = tmp_path / ".gitignore"
    gi.write_text(content, encoding="utf-8")
    return gi


def test_no_trailing_blank_after_block_removal(tmp_path):
    """A blank line that follows _GI_END must be consumed, not left as an orphan."""
    gi = _make_gi(tmp_path, (
        "*.pyc\n"
        "\n"
        f"{_START}\n"
        ".claude/.venv-tokens/\n"
        f"{_END}\n"
        "\n"               # <-- trailing blank after the block
        "dist/\n"
    ))
    install._remove_gitignore_block(gi, dry_run=False)
    result = gi.read_text(encoding="utf-8")
    assert result == "*.pyc\ndist/\n", repr(result)


def test_no_leading_blank_after_block_removal(tmp_path):
    """Existing behaviour: blank line BEFORE the block is also removed."""
    gi = _make_gi(tmp_path, (
        "*.pyc\n"
        "\n"               # preceding blank separator
        f"{_START}\n"
        ".claude/.venv-tokens/\n"
        f"{_END}\n"
        "dist/\n"
    ))
    install._remove_gitignore_block(gi, dry_run=False)
    result = gi.read_text(encoding="utf-8")
    assert result == "*.pyc\ndist/\n", repr(result)
