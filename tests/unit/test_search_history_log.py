"""search.py appends a JSONL audit record per query to search-history.log.

Maintainers had no way to see what Claude searched for or which queries
returned weak results. Every run now appends one best-effort JSON line
(timestamp, query, top score, result count) to .claude/state/
search-history.log - it must never break the search it records.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO))
from tools import search  # noqa: E402


@pytest.fixture()
def state(tmp_path, monkeypatch):
    sd = tmp_path / "state"
    monkeypatch.setattr(search, "STATE_DIR", sd)
    monkeypatch.setattr(search, "HISTORY_LOG", sd / "search-history.log")
    monkeypatch.setattr(search, "_log_savings", lambda *a, **k: None)
    return sd


def _run(argv, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["search.py", *argv])
    assert search.main() == 0


def test_appends_record_with_score_and_count(state, monkeypatch):
    monkeypatch.setattr(
        search, "search",
        lambda *a, **k: [
            {"score": 0.8123456, "source_type": "code", "source_path": "p.py",
             "source_key": "k", "text": "t"},
            {"score": 0.4, "source_type": "code", "source_path": "q.py",
             "source_key": "k", "text": "t"},
        ],
    )
    _run(["my query", "--json"], monkeypatch)

    lines = (state / "search-history.log").read_text().splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["query"] == "my query"
    assert rec["top_score"] == 0.812346
    assert rec["results"] == 2
    assert rec["ts"].endswith("+00:00")


def test_no_results_logs_null_score_and_appends(state, monkeypatch):
    monkeypatch.setattr(search, "search", lambda *a, **k: [])
    _run(["first"], monkeypatch)
    _run(["second"], monkeypatch)

    lines = (state / "search-history.log").read_text().splitlines()
    assert [json.loads(line_)["query"] for line_ in lines] == ["first", "second"]
    assert json.loads(lines[0])["top_score"] is None
    assert json.loads(lines[0])["results"] == 0


def test_log_failure_is_swallowed(tmp_path, monkeypatch):
    # STATE_DIR under a regular file -> mkdir raises OSError; _log_history
    # must absorb it (an audit log can't break the search it records).
    afile = tmp_path / "afile"
    afile.write_text("x")
    monkeypatch.setattr(search, "STATE_DIR", afile / "sub")
    monkeypatch.setattr(search, "HISTORY_LOG", afile / "sub" / "h.log")
    search._log_history("q", [])  # must not raise
