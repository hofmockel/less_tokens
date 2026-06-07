"""Unit tests for the read-guard PreToolUse hook."""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import load_hook

HOOK = Path(__file__).resolve().parent.parent.parent / "hooks" / "read-guard.py"


@pytest.fixture(scope="module")
def hook():
    return load_hook(HOOK)


def test_lockfile_blocked_by_name(hook, tmp_path):
    p = tmp_path / "package-lock.json"
    p.write_text("{}")
    assert hook.check(str(p)) is not None


def test_minified_blocked(hook, tmp_path):
    p = tmp_path / "app.min.js"
    p.write_text("var x=1")
    assert hook.check(str(p)) is not None


def test_binary_blocked_by_content(hook, tmp_path):
    p = tmp_path / "blob.dat"
    p.write_bytes(b"abc\x00def")
    assert hook.check(str(p)) is not None


def test_large_data_blocked(hook, tmp_path):
    p = tmp_path / "big.csv"
    p.write_text("\n".join(f"{i},x" for i in range(hook.READ_DENY_DATA_MAX_LINES + 5)))
    assert hook.check(str(p)) is not None


def test_small_data_allowed(hook, tmp_path):
    p = tmp_path / "small.csv"
    p.write_text("a,b\n1,2\n")
    assert hook.check(str(p)) is None


def test_source_file_allowed(hook, tmp_path):
    p = tmp_path / "main.py"
    p.write_text("def f():\n    return 1\n")
    assert hook.check(str(p)) is None


def test_missing_file_allowed(hook, tmp_path):
    # non-deny path that doesn't exist: let Read raise its own error
    assert hook.check(str(tmp_path / "nope.py")) is None
