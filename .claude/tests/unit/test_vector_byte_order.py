"""Regression: stored embedding vectors must be little-endian on disk so
index.db is portable across host endianness.

The writer used `vec.tobytes()` and the reader `np.frombuffer(..., dtype=
np.float32)` — both host-native. An index built on a little-endian host and
read on a big-endian host (s390x, some POWER/ARM) silently returns wrong
cosine scores: the float32 bytes are reinterpreted with the reader's
endianness. The fix pins the on-disk dtype to little-endian `<f4` at a single
shared serialization point (`pack_vector` / `unpack_vectors`) used by both the
writer (`embeddings.refresh`) and the reader (`search.search`).

Cross-endian behaviour cannot be exercised on a little-endian CI host, so
these tests pin the *contract* (explicit little-endian, host-independent)
rather than the host's native byte order.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(REPO))
from tools import embeddings, search  # noqa: E402
import search_config  # noqa: E402

# search.py imports `connect_index` from the top-level `db` module (tools/ is
# put on sys.path inside search.py); patch INDEX_DB on that exact module.
_DB = sys.modules[search.connect_index.__module__]


class TestSerializationContract:
    def test_pack_is_little_endian_regardless_of_host(self):
        v = np.array([1.0, -2.5, 3.0e9, 0.0], dtype=np.float32)
        # '<f4' forces little-endian on ANY host, so this is a host-independent
        # reference for the required on-disk byte layout.
        assert embeddings.pack_vector(v) == np.asarray(v, dtype="<f4").tobytes()
        # ...and it must NOT be the big-endian layout (these values differ
        # between the two orders), so a revert to native bytes on a
        # big-endian host would fail this assertion.
        assert embeddings.pack_vector(v) != np.asarray(v, dtype=">f4").tobytes()

    def test_round_trip(self):
        v = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6], dtype=np.float32)
        out = embeddings.unpack_vectors(embeddings.pack_vector(v), 3)
        assert out.shape == (2, 3)
        np.testing.assert_array_equal(out.reshape(-1), v)

    def test_unpack_decodes_little_endian_not_native(self):
        # Bytes written little-endian must decode to the original values.
        # Decoding the same bytes big-endian yields different numbers — that
        # is exactly the silent cross-endian corruption this bug is about.
        v = np.array([1.5, 7.25, 1234.5], dtype=np.float32)
        le_bytes = np.asarray(v, dtype="<f4").tobytes()
        np.testing.assert_array_equal(
            embeddings.unpack_vectors(le_bytes, 3).reshape(-1), v
        )
        assert not np.array_equal(np.frombuffer(le_bytes, dtype=">f4"), v)


def _make_index(path: Path, rows: list[tuple]) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE documents (id INTEGER PRIMARY KEY, source_type TEXT, "
        "source_path TEXT, source_key TEXT, text TEXT, embedding BLOB, "
        "embedding_model TEXT)"
    )
    model = search_config.EMBEDDING_MODEL
    conn.executemany(
        "INSERT INTO documents (source_type, source_path, source_key, text, "
        "embedding, embedding_model) VALUES (?, ?, ?, ?, ?, ?)",
        [(*r, model) for r in rows],
    )
    conn.commit()
    conn.close()


class TestSearchReadsThroughSharedContract:
    def test_search_top_result_uses_packed_vectors(self, tmp_path, monkeypatch):
        """End-to-end: vectors written via pack_vector are read back by
        search.search through the same little-endian contract, so the nearest
        chunk ranks first with the expected cosine score.
        """
        dim = embeddings.DIM
        near = np.zeros(dim, dtype=np.float32)
        near[0] = 1.0
        far = np.zeros(dim, dtype=np.float32)
        far[1] = 1.0
        dbp = tmp_path / "index.db"
        _make_index(
            dbp,
            [
                ("code", "near.py", "k", "near", embeddings.pack_vector(near)),
                ("code", "far.py", "k", "far", embeddings.pack_vector(far)),
            ],
        )
        monkeypatch.setattr(_DB, "INDEX_DB", dbp)
        monkeypatch.setattr(search, "embed", lambda *a, **k: np.array([near]))
        hits = search.search("q", k=1)
        assert hits and hits[0]["source_path"] == "near.py"
        assert hits[0]["score"] == pytest.approx(1.0, abs=1e-5)
