"""Unit tests for the grep-first-read hook (S13)."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from tests.conftest import load_hook

HOOK = Path(__file__).resolve().parent.parent.parent / "hooks" / "grep-first-read.py"
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


@pytest.fixture(scope="module")
def hook():
    return load_hook(HOOK)


# ---------------------------------------------------------------------------
# check() — the pure logic function
# ---------------------------------------------------------------------------

def _make_file(tmp_path: Path, n_lines: int, name: str = "big.py") -> Path:
    p = tmp_path / name
    p.write_text("\n".join(f"line {i}" for i in range(1, n_lines + 1)))
    return p


def test_pass_when_offset_given(hook, tmp_path):
    p = _make_file(tmp_path, 500)
    assert hook.check(str(p), offset=1) is None


def test_pass_when_offset_given_nonzero(hook, tmp_path):
    p = _make_file(tmp_path, 500)
    assert hook.check(str(p), offset=100) is None


def test_pass_under_threshold(hook, tmp_path, monkeypatch):
    monkeypatch.setattr(hook, "GREP_FIRST_LINE_THRESHOLD", 150)
    p = _make_file(tmp_path, 100)
    assert hook.check(str(p), offset=None) is None


def test_pass_at_threshold(hook, tmp_path, monkeypatch):
    monkeypatch.setattr(hook, "GREP_FIRST_LINE_THRESHOLD", 150)
    p = _make_file(tmp_path, 150)
    assert hook.check(str(p), offset=None) is None


def test_block_over_threshold(hook, tmp_path, monkeypatch):
    monkeypatch.setattr(hook, "GREP_FIRST_LINE_THRESHOLD", 150)
    p = _make_file(tmp_path, 151)
    result = hook.check(str(p), offset=None)
    assert result is not None
    assert "S13" in result
    assert "151" in result


def test_pass_when_disabled(hook, tmp_path, monkeypatch):
    monkeypatch.setattr(hook, "GREP_FIRST_LINE_THRESHOLD", 0)
    p = _make_file(tmp_path, 9999)
    assert hook.check(str(p), offset=None) is None


def test_pass_nonexistent_file(hook, tmp_path, monkeypatch):
    monkeypatch.setattr(hook, "GREP_FIRST_LINE_THRESHOLD", 150)
    assert hook.check(str(tmp_path / "ghost.py"), offset=None) is None


# ---------------------------------------------------------------------------
# Exemption: in last-search.json (auto-slice handles it)
# ---------------------------------------------------------------------------

def test_exempt_when_in_last_search(hook, tmp_path, monkeypatch):
    monkeypatch.setattr(hook, "GREP_FIRST_LINE_THRESHOLD", 10)
    p = _make_file(tmp_path, 200)
    ranges_file = tmp_path / "last-search.json"
    ranges_file.write_text(json.dumps({str(p): [[5, 15]]}))
    monkeypatch.setattr(hook, "RANGES_FILE", ranges_file)
    monkeypatch.setattr(hook, "WINDOW_SECONDS", 300)
    assert hook.check(str(p), offset=None) is None


def test_exempt_last_search_match_by_name(hook, tmp_path, monkeypatch):
    monkeypatch.setattr(hook, "GREP_FIRST_LINE_THRESHOLD", 10)
    p = _make_file(tmp_path, 200, name="target.py")
    ranges_file = tmp_path / "last-search.json"
    ranges_file.write_text(json.dumps({"tools/target.py": [[1, 10]]}))
    monkeypatch.setattr(hook, "RANGES_FILE", ranges_file)
    monkeypatch.setattr(hook, "WINDOW_SECONDS", 300)
    assert hook.check(str(p), offset=None) is None


def test_not_exempt_when_last_search_stale(hook, tmp_path, monkeypatch):
    monkeypatch.setattr(hook, "GREP_FIRST_LINE_THRESHOLD", 10)
    p = _make_file(tmp_path, 200)
    ranges_file = tmp_path / "last-search.json"
    ranges_file.write_text(json.dumps({str(p): [[5, 15]]}))
    old = time.time() - 10_000
    os.utime(ranges_file, (old, old))
    monkeypatch.setattr(hook, "RANGES_FILE", ranges_file)
    monkeypatch.setattr(hook, "WINDOW_SECONDS", 300)
    result = hook.check(str(p), offset=None)
    assert result is not None  # stale → gate fires


# ---------------------------------------------------------------------------
# Exemption: indexed + no recent search (search-first handles it)
# ---------------------------------------------------------------------------

def test_exempt_indexed_no_recent_search(hook, tmp_path, monkeypatch):
    """Indexed file with no recent search → search-first gates it; S13 stays silent."""
    monkeypatch.setattr(hook, "GREP_FIRST_LINE_THRESHOLD", 10)
    monkeypatch.setattr(hook, "_is_indexed", lambda p: True)
    monkeypatch.setattr(hook, "_search_was_recent", lambda: False)
    p = _make_file(tmp_path, 200)
    assert hook.check(str(p), offset=None) is None


def test_not_exempt_indexed_with_recent_search(hook, tmp_path, monkeypatch):
    """Indexed file after a recent search → search-first passed it; S13 evaluates size."""
    monkeypatch.setattr(hook, "GREP_FIRST_LINE_THRESHOLD", 10)
    monkeypatch.setattr(hook, "_is_indexed", lambda p: True)
    monkeypatch.setattr(hook, "_search_was_recent", lambda: True)
    ranges_file = tmp_path / "last-search.json"
    ranges_file.write_text("{}")
    monkeypatch.setattr(hook, "RANGES_FILE", ranges_file)
    monkeypatch.setattr(hook, "WINDOW_SECONDS", 300)
    p = _make_file(tmp_path, 200)
    result = hook.check(str(p), offset=None)
    assert result is not None


# ---------------------------------------------------------------------------
# main() — JSON payload path
# ---------------------------------------------------------------------------

def _run_main(hook, payload: dict, monkeypatch) -> int:
    import io
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    return hook.main()


def test_main_pass_wrong_tool(hook, monkeypatch, tmp_path):
    code = _run_main(hook, {"tool_name": "Bash", "tool_input": {}}, monkeypatch)
    assert code == 0


def test_main_block_large_file(hook, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(hook, "GREP_FIRST_LINE_THRESHOLD", 10)
    p = _make_file(tmp_path, 200)
    ranges_file = tmp_path / "last-search.json"
    ranges_file.write_text("{}")
    monkeypatch.setattr(hook, "RANGES_FILE", ranges_file)
    monkeypatch.setattr(hook, "WINDOW_SECONDS", 300)
    monkeypatch.setattr(hook, "_is_indexed", lambda path: False)
    code = _run_main(hook, {"tool_name": "Read", "tool_input": {"file_path": str(p)}}, monkeypatch)
    assert code == 2
    assert "S13" in capsys.readouterr().err


def test_main_pass_with_offset(hook, monkeypatch, tmp_path):
    monkeypatch.setattr(hook, "GREP_FIRST_LINE_THRESHOLD", 10)
    p = _make_file(tmp_path, 200)
    code = _run_main(hook, {"tool_name": "Read", "tool_input": {"file_path": str(p), "offset": 50}}, monkeypatch)
    assert code == 0
