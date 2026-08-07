"""Bug: duplication() fetches all rows regardless of embedding_model.

After a model switch the index contains rows with different vector dimensions.
np.vstack raises ValueError when dimensions differ; the outer except catches it
and returns None, silently disabling duplicate detection.

The fix: add WHERE embedding_model = ? so only same-model rows are stacked.
"""

from __future__ import annotations

import sqlite3
import struct
import sys
from pathlib import Path

import numpy as np
import pytest

TOOLS = Path(__file__).parent.parent.parent / "tools"
sys.path.insert(0, str(TOOLS))

import search_config  # noqa: E402


CURRENT_MODEL = "model-current"
STALE_MODEL = "model-stale"
CURRENT_DIM = 4
STALE_DIM = 8  # different dimension → vstack fails if mixed


def _pack(v: list[float]) -> bytes:
    """Pack float list as little-endian float32 blob (no marker prefix)."""
    return struct.pack(f"<{len(v)}f", *v)


@pytest.fixture()
def mixed_model_db(tmp_path, monkeypatch):
    """Index with rows from two models with incompatible vector dimensions."""
    dbp = tmp_path / "index.db"
    conn = sqlite3.connect(dbp)
    conn.execute(
        "CREATE TABLE documents ("
        "id INTEGER PRIMARY KEY, source_type TEXT, "
        "source_path TEXT, source_key TEXT, text TEXT, "
        "content_hash TEXT, embedding BLOB, embedding_model TEXT, updated_at TEXT)"
    )
    # current-model row (dim=4)
    conn.execute(
        "INSERT INTO documents (source_type, source_path, source_key, text, "
        "content_hash, embedding, embedding_model, updated_at) VALUES (?,?,?,?,?,?,?,?)",
        (
            "doc",
            "notes.md",
            "sec_a",
            "some content",
            "h1",
            _pack([0.1, 0.2, 0.3, 0.4]),
            CURRENT_MODEL,
            "2025-01-01",
        ),
    )
    # stale-model row (dim=8) — would cause vstack ValueError if mixed
    conn.execute(
        "INSERT INTO documents (source_type, source_path, source_key, text, "
        "content_hash, embedding, embedding_model, updated_at) VALUES (?,?,?,?,?,?,?,?)",
        (
            "doc",
            "stale.md",
            "sec_b",
            "stale content",
            "h2",
            _pack([0.1] * 8),
            STALE_MODEL,
            "2024-01-01",
        ),
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(search_config, "EMBEDDING_MODEL", CURRENT_MODEL)
    return dbp


def test_duplication_filters_by_model(mixed_model_db, monkeypatch):
    """duplication() must not crash when stale-model rows exist in the index."""
    import claudemd_audit
    import db as db_mod

    # Patch INDEX_DB to point at our test db
    monkeypatch.setattr(db_mod, "INDEX_DB", mixed_model_db)

    sections = [{"level": 1, "title": "sec_a", "body": "some content", "_tokens": 10}]

    # Stub embed so we don't need fastembed installed
    fake_q = np.array([[0.1, 0.2, 0.3, 0.4]], dtype="float32")

    def fake_embed(texts, **kw):
        return fake_q

    def fake_unpack(blob, dim):
        vals = struct.unpack(f"<{len(blob) // 4}f", blob)
        return np.array(vals, dtype="float32")

    import embeddings as emb_mod

    monkeypatch.setattr(emb_mod, "DIM", CURRENT_DIM)

    def safe_unpack(blob, dim):
        return fake_unpack(blob, dim)

    monkeypatch.setattr(emb_mod, "unpack_vectors", safe_unpack)
    monkeypatch.setattr(emb_mod, "embed", fake_embed)

    # With the bug, this raises ValueError (vstack on mismatched dims)
    # caught by except Exception → returns None unexpectedly.
    # With the fix it returns a dict (not None) because the stale row is excluded.
    result = claudemd_audit.duplication(sections)

    # Result must not be None — stale row excluded, so vstack succeeds
    assert result is not None, (
        "duplication() returned None — likely crashed on mixed-dimension vstack "
        "(Bug: missing embedding_model filter)"
    )
