"""Bug 18: search.py returned mixed-model results with garbage scores.

When the index contains rows from multiple embedding models (e.g., after a
model switch without a full re-index), computing cosine similarity between a
query vector from model B and stored vectors from model A produces garbage
scores.  search() must filter to only rows whose embedding_model matches the
currently-configured model.
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

CURRENT_MODEL = "model-current"
STALE_MODEL = "model-stale"


def _vec(scale: float) -> bytes:
    v = np.zeros(search.DIM, dtype="<f4")
    v[0] = scale
    return v.tobytes()


@pytest.fixture()
def mixed_model_db(tmp_path, monkeypatch):
    """Index with rows from two different embedding models."""
    dbp = tmp_path / "index.db"
    conn = sqlite3.connect(dbp)
    conn.execute(
        "CREATE TABLE documents ("
        "id INTEGER PRIMARY KEY, source_type TEXT, "
        "source_path TEXT, source_key TEXT, text TEXT, "
        "embedding BLOB, embedding_model TEXT)"
    )
    conn.executemany(
        "INSERT INTO documents (source_type, source_path, source_key, text, "
        "embedding, embedding_model) VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("code", "good.py", "fn_a", "correct result", _vec(0.9), CURRENT_MODEL),
            ("code", "stale.py", "fn_b", "stale model row", _vec(0.8), STALE_MODEL),
        ],
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(_DB, "INDEX_DB", dbp)
    monkeypatch.setattr(search_config, "EMBEDDING_MODEL", CURRENT_MODEL)
    q = np.zeros(search.DIM, dtype=np.float32)
    q[0] = 1.0
    monkeypatch.setattr(search, "embed", lambda *a, **k: np.array([q]))
    return dbp


def test_search_excludes_stale_model_rows(mixed_model_db):
    """search() must not return rows whose embedding_model != current model."""
    hits = search.search("anything", k=10)
    paths = [h["source_path"] for h in hits]
    assert "stale.py" not in paths, (
        "search() returned rows from a stale/different embedding model (Bug 18)"
    )
    assert "good.py" in paths
