"""search.py logs a near-miss when the same query repeats in a session.

BACKLOG.md's "Same-session search.py repeated-query cache" item requires
measuring real repeat-query frequency before building a cache. This is
additive-only telemetry (agents/common/hooks/context_cache.py's
record_near_miss precedent): it must never block a search or change its
results, only append to state/near_misses.jsonl on an exact repeat.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(REPO))
from tools import search  # noqa: E402


@pytest.fixture()
def state(tmp_path, monkeypatch):
    sd = tmp_path / "state"
    monkeypatch.setattr(search, "active_state_dir", lambda: sd)
    monkeypatch.setattr(search, "_log_savings", lambda *a, **k: None)
    monkeypatch.setattr(search, "search", lambda *a, **k: [])
    monkeypatch.setattr(search, "_resolve_session", lambda raw: ("sess-1", "env"))
    return sd


def _run(query, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["search.py", query])
    assert search.main() == 0


def test_first_query_logs_no_near_miss(state, monkeypatch):
    _run("wash sale", monkeypatch)
    assert not (state / "near_misses.jsonl").exists()


def test_repeated_query_in_session_logs_near_miss(state, monkeypatch):
    _run("wash sale", monkeypatch)
    _run("wash sale", monkeypatch)

    lines = (state / "near_misses.jsonl").read_text().splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["kind"] == "search"
    assert rec["signature"] == "wash sale"
    assert rec["session_id"] == "sess-1"


def test_different_query_does_not_log_near_miss(state, monkeypatch):
    _run("wash sale", monkeypatch)
    _run("cash floor", monkeypatch)
    assert not (state / "near_misses.jsonl").exists()


def test_near_miss_scoped_to_session(state, monkeypatch):
    monkeypatch.setattr(search, "_resolve_session", lambda raw: ("sess-1", "env"))
    _run("wash sale", monkeypatch)
    monkeypatch.setattr(search, "_resolve_session", lambda raw: ("sess-2", "env"))
    _run("wash sale", monkeypatch)
    assert not (state / "near_misses.jsonl").exists()


def test_near_miss_failure_is_swallowed(tmp_path, monkeypatch):
    afile = tmp_path / "afile"
    afile.write_text("x")
    search._record_search_near_miss(afile / "sub", "q", "sess-1")  # must not raise
