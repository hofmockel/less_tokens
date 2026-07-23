"""HS2: production search fuses lexical and vector ranks via RRF."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(REPO))
from tools import db as db_mod  # noqa: E402
from tools import search  # noqa: E402
import search_config  # noqa: E402

_SEARCH_DB = sys.modules[search.connect_index.__module__]


def _vec(score: float, axis: int = 0) -> bytes:
    value = np.zeros(search.DIM, dtype="<f4")
    value[axis] = score
    return value.tobytes()


@pytest.fixture()
def hybrid_index(tmp_path, monkeypatch):
    db_path = tmp_path / "index.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE documents (id INTEGER PRIMARY KEY, source_type TEXT, "
        "source_path TEXT, source_key TEXT, text TEXT, embedding BLOB, "
        "embedding_model TEXT)"
    )
    conn.execute("CREATE VIRTUAL TABLE documents_fts USING fts5(text)")
    model = search_config.EMBEDDING_MODEL
    rows = [
        (1, "code", "vector.py", "vector", "generic retrieval", _vec(0.9, 0), model),
        (2, "code", "lexical.py", "lexical", "rare_exact_symbol", _vec(0.2, 1), model),
        (3, "code", "other.py", "other", "unrelated content", _vec(0.1, 2), model),
    ]
    conn.executemany("INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?, ?)", rows)
    conn.executemany(
        "INSERT INTO documents_fts(rowid, text) VALUES (?, ?)",
        [(row[0], row[4]) for row in rows],
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(_SEARCH_DB, "INDEX_DB", db_path)
    query = np.zeros(search.DIM, dtype=np.float32)
    query[:3] = 1.0
    monkeypatch.setattr(search, "embed", lambda *args, **kwargs: np.array([query]))
    return db_path


def test_bughs2_rrf_promotes_exact_lexical_match(hybrid_index):
    hits = search.search("rare_exact_symbol", k=2)

    assert [hit["source_path"] for hit in hits] == ["lexical.py", "vector.py"]


def test_bughs2_schema_keeps_fts_in_sync(tmp_path, monkeypatch):
    db_path = tmp_path / "index.db"
    monkeypatch.setattr(db_mod, "INDEX_DB", db_path)
    assert db_mod.init() == 0

    with db_mod.connect_index() as conn:
        conn.execute(
            "INSERT INTO documents "
            "(source_type, source_path, source_key, text, content_hash, embedding, "
            "embedding_model, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("code", "a.py", "a", "first token", "hash", _vec(1.0), "model", "now"),
        )
        assert (
            conn.execute(
                "SELECT text FROM documents_fts WHERE documents_fts MATCH 'first'"
            ).fetchone()[0]
            == "first token"
        )
        conn.execute(
            "UPDATE documents SET text = 'second token' WHERE source_path = 'a.py'"
        )
        assert (
            conn.execute(
                "SELECT text FROM documents_fts WHERE documents_fts MATCH 'second'"
            ).fetchone()[0]
            == "second token"
        )
        conn.execute("DELETE FROM documents WHERE source_path = 'a.py'")
        assert conn.execute("SELECT count(*) FROM documents_fts").fetchone()[0] == 0


def test_bughs2_migration_backfills_existing_documents(tmp_path, monkeypatch):
    db_path = tmp_path / "index.db"
    monkeypatch.setattr(db_mod, "INDEX_DB", db_path)
    conn = sqlite3.connect(db_path)
    conn.executescript(db_mod.SCHEMA_FILE.read_text(encoding="utf-8"))
    conn.execute("DELETE FROM schema_version")
    conn.execute("INSERT INTO schema_version VALUES (2, 'then')")
    conn.execute(
        "INSERT INTO documents "
        "(source_type, source_path, source_key, text, content_hash, embedding, "
        "embedding_model, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("code", "old.py", "old", "existing token", "hash", _vec(1.0), "model", "then"),
    )
    conn.execute("DROP TABLE IF EXISTS documents_fts")
    conn.commit()
    conn.close()

    assert db_mod.migrate() == 0
    with db_mod.connect_index() as conn:
        assert (
            conn.execute(
                "SELECT text FROM documents_fts WHERE documents_fts MATCH 'existing'"
            ).fetchone()[0]
            == "existing token"
        )
