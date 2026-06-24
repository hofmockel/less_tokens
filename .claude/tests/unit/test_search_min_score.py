"""search.py --min-score: drop results below a cosine-score threshold.

Without a floor, the top-k always returns k chunks even when the best match
is semantically unrelated, so Claude can act on noise. `--min-score X` filters
the top-k to scores >= X (and the `search()` function takes a `min_score`
kwarg). This test crafts a tiny index with known dot-product scores and
asserts the threshold both filters results and is wired through argparse.
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
    # Distinct paths on distinct axes so the cross-file dedup (SEARCH_DEDUP_SIM)
    # doesn't collapse these as near-duplicates; only the score floor is exercised.
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
            ("code", "p/hi.py", "hi", "high", _vec(0.9, 0), model),
            ("code", "p/mid.py", "mid", "mid", _vec(0.4, 1), model),
            ("code", "p/lo.py", "lo", "low", _vec(0.1, 2), model),
        ],
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(_DB, "INDEX_DB", dbp)
    # Query hits each file's axis, so score == that file's stored scale.
    q = np.zeros(search.DIM, dtype=np.float32)
    q[0] = q[1] = q[2] = 1.0
    monkeypatch.setattr(search, "embed", lambda *a, **k: np.array([q]))
    return dbp


def test_min_score_filters_low_confidence(index_db):
    all_hits = search.search("q", k=3)
    assert [r["source_key"] for r in all_hits] == ["hi", "mid", "lo"]

    floored = search.search("q", k=3, min_score=0.5)
    assert [r["source_key"] for r in floored] == ["hi"]


def test_min_score_none_keeps_all(index_db):
    assert len(search.search("q", k=3, min_score=None)) == 3


def test_argparse_accepts_min_score(index_db, tmp_path, monkeypatch):
    captured = {}
    monkeypatch.setattr(search, "active_state_dir", lambda: tmp_path / "state")
    real = search.search

    def spy(*a, **k):
        captured["min_score"] = k.get("min_score")
        return real(*a, **k)

    monkeypatch.setattr(search, "search", spy)
    monkeypatch.setattr(
        sys, "argv", ["search.py", "q", "--min-score", "0.5", "--json"]
    )
    assert search.main() == 0
    assert captured["min_score"] == 0.5
