"""search.py collapses same-file chunks and backfills k with unique files.

When two top-k chunks share a source_path, returning both spends context
budget on near-duplicate text from one file while a distinct file drops off
the list. search() now keeps the best-scoring chunk per source_path and
pulls the next distinct file in to fill k.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(REPO))
from tools import search  # noqa: E402

_DB = sys.modules[search.connect_index.__module__]


def _vec(scale: float) -> bytes:
    v = np.zeros(search.DIM, dtype="<f4")
    v[0] = scale
    return v.tobytes()


@pytest.fixture()
def index_db(tmp_path, monkeypatch):
    dbp = tmp_path / "index.db"
    conn = sqlite3.connect(dbp)
    conn.execute(
        "CREATE TABLE documents (id INTEGER PRIMARY KEY, source_type TEXT, "
        "source_path TEXT, source_key TEXT, text TEXT, embedding BLOB)"
    )
    conn.executemany(
        "INSERT INTO documents (source_type, source_path, source_key, text, "
        "embedding) VALUES (?, ?, ?, ?, ?)",
        [
            ("code", "p/a.py", "a1", "a-one", _vec(0.9)),
            ("code", "p/a.py", "a2", "a-two", _vec(0.8)),
            ("code", "p/b.py", "b1", "b-one", _vec(0.7)),
            ("code", "p/c.py", "c1", "c-one", _vec(0.3)),
        ],
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(_DB, "INDEX_DB", dbp)
    q = np.zeros(search.DIM, dtype=np.float32)
    q[0] = 1.0
    monkeypatch.setattr(search, "embed", lambda *a, **k: np.array([q]))
    return dbp


def test_collapses_same_path_and_backfills(index_db):
    hits = search.search("q", k=2)
    # Pre-fix this returned [a1, a2]; now it's the best chunk of a then b.
    assert [(h["source_path"], h["source_key"]) for h in hits] == [
        ("p/a.py", "a1"),
        ("p/b.py", "b1"),
    ]


def test_unique_paths_in_results(index_db):
    hits = search.search("q", k=3)
    paths = [h["source_path"] for h in hits]
    assert paths == ["p/a.py", "p/b.py", "p/c.py"]
    assert len(paths) == len(set(paths))


def test_min_score_still_applies_after_dedup(index_db):
    hits = search.search("q", k=3, min_score=0.5)
    assert [h["source_path"] for h in hits] == ["p/a.py", "p/b.py"]
