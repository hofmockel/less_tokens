"""Unit tests for the auto-slice hook + search.py range writer (S9)."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from tests.conftest import load_hook

HOOK = Path(__file__).resolve().parent.parent.parent / "hooks" / "auto-slice.py"


@pytest.fixture(scope="module")
def hook():
    return load_hook(HOOK)


def _write_ranges(tmp_path, data):
    f = tmp_path / "last-search.json"
    f.write_text(json.dumps(data))
    return f


def test_ranges_for_match_by_name(hook, tmp_path, monkeypatch):
    rf = _write_ranges(tmp_path, {"tools/foo.py": [[10, 20]]})
    monkeypatch.setattr(hook, "RANGES_FILE", rf)
    monkeypatch.setattr(hook, "WINDOW_SECONDS", 300)
    assert hook._ranges_for("/abs/tools/foo.py") == [[10, 20]]


def test_ranges_for_miss(hook, tmp_path, monkeypatch):
    rf = _write_ranges(tmp_path, {"tools/foo.py": [[10, 20]]})
    monkeypatch.setattr(hook, "RANGES_FILE", rf)
    monkeypatch.setattr(hook, "WINDOW_SECONDS", 300)
    assert hook._ranges_for("/abs/tools/bar.py") == []


def test_ranges_for_stale_window(hook, tmp_path, monkeypatch):
    rf = _write_ranges(tmp_path, {"foo.py": [[1, 5]]})
    old = time.time() - 10_000
    import os

    os.utime(rf, (old, old))
    monkeypatch.setattr(hook, "RANGES_FILE", rf)
    monkeypatch.setattr(hook, "WINDOW_SECONDS", 300)
    assert hook._ranges_for("foo.py") == []  # too old → no slice


def test_search_locate_range(tmp_path):
    import sys

    tools = Path(__file__).resolve().parent.parent.parent / "tools"
    if str(tools) not in sys.path:
        sys.path.insert(0, str(tools))
    import search

    ft = "\n".join(f"line{i}" for i in range(1, 21))
    assert search._locate_range(ft, "line5\nline6\nline7") == (5, 7)
    assert search._locate_range(ft, "nope") is None


def test_search_writes_ranges(tmp_path, monkeypatch):
    import sys

    tools = Path(__file__).resolve().parent.parent.parent / "tools"
    if str(tools) not in sys.path:
        sys.path.insert(0, str(tools))
    import search

    src = tmp_path / "m.py"
    src.write_text("\n".join(f"line{i}" for i in range(1, 21)))
    monkeypatch.setattr(search, "BASE", tmp_path)
    monkeypatch.setattr(search, "active_state_dir", lambda: tmp_path / "state")
    search._write_last_search_ranges(
        [{"source_path": "m.py", "text": "line5\nline6\nline7"}]
    )
    data = json.loads((tmp_path / "state" / "last-search.json").read_text())
    assert data["m.py"] == [[5, 7]]
