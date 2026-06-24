"""search.py drops a hit whose vector is near-identical to one already selected (G10).

Same-file collapse (test_search_dedup.py) keys on source_path. This adds *cross-file*
dedup: two distinct files whose best chunks embed almost identically would both spend
context budget on the same content. search() now skips the second and backfills the
next distinct hit. Controlled by search_config.SEARCH_DEDUP_SIM (>= 1.0 disables it).
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
import search_config  # noqa: E402

_DB = sys.modules[search.connect_index.__module__]


def _vec(scale: float, axis: int = 0) -> bytes:
    v = np.zeros(search.DIM, dtype="<f4")
    v[axis] = scale
    return v.tobytes()


@pytest.fixture()
def index_db(tmp_path, monkeypatch):
    dbp = tmp_path / "index.db"
    conn = sqlite3.connect(dbp)
    conn.execute(
        "CREATE TABLE documents (id INTEGER PRIMARY KEY, source_type TEXT, "
        "source_path TEXT, source_key TEXT, text TEXT, embedding BLOB, "
        "embedding_model TEXT)"
    )
    model = search_config.EMBEDDING_MODEL
    conn.executemany(
        "INSERT INTO documents (source_type, source_path, source_key, text, "
        "embedding, embedding_model) VALUES (?, ?, ?, ?, ?, ?)",
        [
            # a and d are different files but collinear → near-duplicate content.
            ("code", "p/a.py", "a1", "a-one", _vec(0.9, 0), model),
            ("code", "p/d.py", "d1", "d-one", _vec(0.85, 0), model),
            # b is on a distinct axis → not a duplicate of either.
            ("code", "p/b.py", "b1", "b-one", _vec(0.7, 1), model),
        ],
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(_DB, "INDEX_DB", dbp)
    q = np.zeros(search.DIM, dtype=np.float32)
    q[0] = q[1] = 1.0
    monkeypatch.setattr(search, "embed", lambda *a, **k: np.array([q]))
    return dbp


def test_near_duplicate_file_dropped_and_backfilled(index_db, monkeypatch):
    monkeypatch.setattr(search_config, "SEARCH_DEDUP_SIM", 0.97)
    hits = search.search("q", k=2)
    # d.py is near-identical to a.py, so it's dropped and b.py backfills the slot.
    assert [h["source_path"] for h in hits] == ["p/a.py", "p/b.py"]


def test_dedup_disabled_keeps_near_duplicate(index_db, monkeypatch):
    monkeypatch.setattr(search_config, "SEARCH_DEDUP_SIM", 1.0)
    hits = search.search("q", k=2)
    # With dedup off, the second-best hit (the near-duplicate) stays.
    assert [h["source_path"] for h in hits] == ["p/a.py", "p/d.py"]
