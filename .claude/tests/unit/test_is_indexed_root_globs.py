"""Regression: is_indexed() in search-first.py must consult INDEXED_ROOT_GLOBS.

The hardcoded check `rel.endswith((".md", ".py", ".sql"))` ignores
_config["root_globs"]; if a user configures INDEXED_ROOT_GLOBS differently
the gate is out of sync with the indexer.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import load_hook

HOOK = Path(__file__).resolve().parent.parent.parent / "hooks" / "search-first.py"


@pytest.fixture(scope="module")
def hook():
    return load_hook(HOOK)


def _set_root_globs(hook, globs: tuple, tmp_repo: Path) -> None:
    """Patch _config in the loaded hook module."""
    hook._config.clear()
    hook._config.update(
        {
            "root_globs": globs,
            "dirs": [],
            "excluded_prefixes": [],
            "excluded_names": [],
            "state_file": tmp_repo / ".claude" / "state" / "last-search",
            "window_seconds": 120,
        }
    )
    # Override REPO so relative_to() works
    hook.REPO = tmp_repo


def test_root_glob_md_matches(hook, tmp_path):
    """Default *.md glob must match a root .md file."""
    _set_root_globs(hook, ("*.md",), tmp_path)
    f = tmp_path / "README.md"
    f.write_text("# hi")
    assert hook.is_indexed(f) is True


def test_root_glob_custom_pattern_matches(hook, tmp_path):
    """A custom root glob like *.txt must match .txt files."""
    _set_root_globs(hook, ("*.txt",), tmp_path)
    f = tmp_path / "notes.txt"
    f.write_text("hello")
    assert hook.is_indexed(f) is True


def test_root_glob_custom_pattern_rejects_other_suffix(hook, tmp_path):
    """When root_globs is only *.txt, .py root files must NOT be indexed."""
    _set_root_globs(hook, ("*.txt",), tmp_path)
    f = tmp_path / "script.py"
    f.write_text("x = 1")
    # Under the old hardcoded logic .py was always True; now it must be False
    assert hook.is_indexed(f) is False


def test_root_glob_empty_tuple_rejects_all(hook, tmp_path):
    """Empty root_globs means no root files are indexed."""
    _set_root_globs(hook, (), tmp_path)
    f = tmp_path / "README.md"
    f.write_text("# hi")
    assert hook.is_indexed(f) is False
