"""Regression: is_indexed() in index-refresh.py must consult INDEXED_ROOT_GLOBS.

Hardcoded `rel.endswith((".md", ".py", ".sql"))` at index-refresh.py:90 ignores
INDEXED_ROOT_GLOBS, triggering spurious re-embeds for non-indexed root files.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import load_hook

HOOK = Path(__file__).resolve().parent.parent.parent / "hooks" / "index-refresh.py"


@pytest.fixture(scope="module")
def hook():
    return load_hook(HOOK)


def _patch(hook, tmp_repo: Path, root_globs: tuple) -> None:
    hook.REPO = tmp_repo
    hook.INDEXED_ROOT_GLOBS = root_globs
    hook.INDEXED_DIRS = ()
    hook.EXCLUDED_DIR_PREFIXES = ()
    hook.EXCLUDED_DIR_NAMES = set()


def test_root_md_matches_default(hook, tmp_path):
    """Default *.md glob indexes root .md files."""
    _patch(hook, tmp_path, ("*.md",))
    f = tmp_path / "README.md"
    f.write_text("# hi")
    assert hook.is_indexed(f) is True


def test_custom_glob_txt_matches(hook, tmp_path):
    """Custom *.txt glob indexes root .txt files."""
    _patch(hook, tmp_path, ("*.txt",))
    f = tmp_path / "notes.txt"
    f.write_text("hi")
    assert hook.is_indexed(f) is True


def test_custom_glob_rejects_py(hook, tmp_path):
    """When INDEXED_ROOT_GLOBS is only *.txt, root .py must NOT be indexed."""
    _patch(hook, tmp_path, ("*.txt",))
    f = tmp_path / "script.py"
    f.write_text("x = 1")
    # old hardcoded logic: .py → True; correct: False
    assert hook.is_indexed(f) is False


def test_empty_root_globs_rejects_all(hook, tmp_path):
    """Empty INDEXED_ROOT_GLOBS means no root files are indexed."""
    _patch(hook, tmp_path, ())
    f = tmp_path / "README.md"
    f.write_text("# hi")
    assert hook.is_indexed(f) is False
