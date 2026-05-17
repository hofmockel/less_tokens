"""embeddings.py stats --verbose: index age, file count, coverage.

Plain `stats` only printed per-source_type row counts, so there was no
quick way to see whether the index was fresh or how much of the expected
source set it covered. `--verbose` adds indexed-file count, index age
(from the newest chunk's updated_at), and coverage vs expected sources.
Plain `stats` output is unchanged.
"""
from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO))
from tools import embeddings  # noqa: E402

_DB = sys.modules[embeddings.connect_index.__module__]


@pytest.fixture()
def index_db(tmp_path, monkeypatch):
    dbp = tmp_path / "index.db"
    conn = sqlite3.connect(dbp)
    conn.execute(
        "CREATE TABLE documents (id INTEGER PRIMARY KEY, source_type TEXT, "
        "source_path TEXT, source_key TEXT, text TEXT, content_hash TEXT, "
        "embedding BLOB, embedding_model TEXT, updated_at TEXT)"
    )
    old = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
    conn.executemany(
        "INSERT INTO documents (source_type, source_path, source_key, "
        "updated_at) VALUES (?, ?, ?, ?)",
        [
            ("code", "tools/a.py", "f", old),
            ("code", "tools/a.py", "g", old),
            ("doc", "README.md", "h", old),
        ],
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(_DB, "INDEX_DB", dbp)
    monkeypatch.setattr(
        embeddings, "expected_source_paths",
        lambda: {"tools/a.py", "README.md", "schema/x.sql"},
    )
    return dbp


def test_plain_stats_unchanged(index_db, capsys):
    assert embeddings.stats() == 0
    out = capsys.readouterr().out
    assert "index.db documents: 3" in out
    assert "code" in out and "doc" in out
    assert "coverage" not in out
    assert "index age" not in out


def test_verbose_adds_age_files_and_coverage(index_db, capsys):
    assert embeddings.stats(verbose=True) == 0
    out = capsys.readouterr().out
    assert "indexed files: 2" in out
    assert "index age: 5h" in out
    # 2 of 3 expected paths present (schema/x.sql missing).
    assert "coverage: 2/3 expected sources (67%)" in out
    assert "missing: schema/x.sql" in out


def test_verbose_via_argv(index_db, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["embeddings.py", "stats", "--verbose"])
    assert embeddings.main() == 0
    assert "coverage:" in capsys.readouterr().out


def test_format_age_thresholds():
    assert embeddings._format_age(5) == "5s"
    assert embeddings._format_age(120) == "2m"
    assert embeddings._format_age(7200) == "2h"
    assert embeddings._format_age(200000) == "2d"
