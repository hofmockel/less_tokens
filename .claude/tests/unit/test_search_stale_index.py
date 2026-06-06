"""search.py warns when index.db is older than an indexed source file.

Without a freshness signal, Claude can act on results from a stale index
after editing source (the auto-refresh hook can lag or fail). search.py now
compares the newest indexed source-file mtime against index.db's mtime and
prints a one-line warning to stderr (never stdout/JSON) before results.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(REPO))
from tools import search  # noqa: E402

_DB = sys.modules[search.connect_index.__module__]


@pytest.fixture()
def index_db(tmp_path, monkeypatch):
    dbp = tmp_path / "index.db"
    conn = sqlite3.connect(dbp)
    conn.execute(
        "CREATE TABLE documents (id INTEGER PRIMARY KEY, source_type TEXT, "
        "source_path TEXT, source_key TEXT, text TEXT, embedding BLOB)"
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(_DB, "INDEX_DB", dbp)
    monkeypatch.setattr(search, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(search, "search", lambda *a, **k: [])
    return dbp


def test_stale_when_source_newer_than_index(index_db):
    idx_mtime = index_db.stat().st_mtime
    monkeypatch_now = idx_mtime + 100
    import unittest.mock as m

    with m.patch.object(search, "_newest_source_mtime", return_value=monkeypatch_now):
        assert search._index_is_stale() is True


def test_fresh_when_index_newer_than_source(index_db):
    idx_mtime = index_db.stat().st_mtime
    import unittest.mock as m

    with m.patch.object(search, "_newest_source_mtime", return_value=idx_mtime - 100):
        assert search._index_is_stale() is False


def test_missing_index_is_not_reported_stale(tmp_path, monkeypatch):
    monkeypatch.setattr(_DB, "INDEX_DB", tmp_path / "nope.db")
    assert search._index_is_stale() is False


def test_main_emits_stderr_warning_when_stale(index_db, monkeypatch, capsys):
    import unittest.mock as m

    monkeypatch.setattr(sys, "argv", ["search.py", "q", "--json"])
    with m.patch.object(search, "_index_is_stale", return_value=True):
        assert search.main() == 0
    err = capsys.readouterr().err
    assert "stale" in err.lower()
    assert "refresh" in err
