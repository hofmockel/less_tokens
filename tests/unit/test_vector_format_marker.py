"""Regression: an index.db written before embeddings were pinned
little-endian must be rebuilt, not silently served as corrupt scores.

Vectors are now (de)serialized as little-endian `<f4` (4e53469). An
`index.db` built before that pin on a big-endian host stored native
big-endian bytes; `refresh()` skips rows whose *text* content_hash is
unchanged, so those blobs are never rewritten, yet `search` now decodes
every blob little-endian — silently wrong cosine scores until a manual
full rebuild.

The fix stamps a vector-format marker in `PRAGMA user_version`. `refresh()`
force-rebuilds an index that predates the marker (one shot), then stamps
it; marked indexes refresh incrementally as before. The forced rebuild is
deferred (not performed, marker not stamped) when enumeration was
incomplete, so it composes with the unreadable-dir handling rather than
deleting rows it cannot re-embed.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO))
from tools import embeddings  # noqa: E402

_DB = sys.modules[embeddings.connect_index.__module__]


def _user_version(dbp) -> int:
    c = sqlite3.connect(dbp)
    try:
        return c.execute("PRAGMA user_version").fetchone()[0]
    finally:
        c.close()


def _set_user_version(dbp, v: int) -> None:
    c = sqlite3.connect(dbp)
    try:
        c.execute(f"PRAGMA user_version = {int(v)}")
        c.commit()
    finally:
        c.close()


def _seed(dbp, sp, sk, text, embedding: bytes) -> None:
    c = sqlite3.connect(dbp)
    try:
        c.execute(
            "INSERT INTO documents (source_type, source_path, source_key, "
            "text, content_hash, embedding, embedding_model, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("code", sp, sk, text, embeddings._sha256(text), embedding,
             embeddings.MODEL, "2026-01-01T00:00:00+00:00"),
        )
        c.commit()
    finally:
        c.close()


def _embedding_of(dbp, sp, sk):
    c = sqlite3.connect(dbp)
    try:
        row = c.execute(
            "SELECT embedding FROM documents "
            "WHERE source_path=? AND source_key=?",
            (sp, sk),
        ).fetchone()
        return row[0] if row else None
    finally:
        c.close()


def _row_exists(dbp, sp, sk) -> bool:
    c = sqlite3.connect(dbp)
    try:
        return c.execute(
            "SELECT 1 FROM documents WHERE source_path=? AND source_key=?",
            (sp, sk),
        ).fetchone() is not None
    finally:
        c.close()


@pytest.fixture()
def temp_index(tmp_path, monkeypatch):
    dbp = tmp_path / "index.db"
    monkeypatch.setattr(_DB, "INDEX_DB", dbp)
    _DB.init()  # real schema; PRAGMA user_version starts at 0
    return dbp


def _no_model(monkeypatch, vec=None):
    monkeypatch.setattr(embeddings, "_get_model", lambda: None)
    out = np.ones(embeddings.DIM, dtype=np.float32) if vec is None else vec
    monkeypatch.setattr(
        embeddings, "embed",
        lambda texts, *a, **k: np.stack([out] * len(texts)),
    )


def test_clean_refresh_stamps_marker(temp_index, monkeypatch):
    """A complete refresh stamps the current vector-format marker so later
    runs know the index is in the current on-disk layout.
    """
    _no_model(monkeypatch)
    monkeypatch.setattr(embeddings, "enumerate_sources", lambda: ([], False))

    assert _user_version(temp_index) == 0
    assert embeddings.refresh() == 0
    assert _user_version(temp_index) == embeddings.VEC_FORMAT


def test_pre_pin_index_forces_reembed(temp_index, monkeypatch):
    """An unmarked index (user_version 0) with an otherwise-unchanged row is
    force-re-embedded — the stale-layout blob is replaced, not skipped.
    """
    text = "def f():\n    return 1\n"
    old_blob = b"OLD-NATIVE-ENDIAN-BYTES"
    _seed(temp_index, "good/ok.py", "f", text, old_blob)
    assert _user_version(temp_index) == 0  # simulates a pre-pin index

    new_vec = np.full(embeddings.DIM, 0.5, dtype=np.float32)
    _no_model(monkeypatch, vec=new_vec)
    monkeypatch.setattr(
        embeddings, "enumerate_sources",
        lambda: ([("code", "good/ok.py", "f", text)], False),
    )

    assert embeddings.refresh() == 0

    stored = _embedding_of(temp_index, "good/ok.py", "f")
    assert stored == embeddings.pack_vector(new_vec), \
        "stale-layout blob must be re-embedded, not skipped on content match"
    assert _user_version(temp_index) == embeddings.VEC_FORMAT


def test_marked_index_skips_forced_reembed(temp_index, monkeypatch):
    """Guard: a marked index must NOT be wiped/re-embedded every refresh —
    an unchanged row keeps its existing (current-format) embedding.
    """
    _set_user_version(temp_index, embeddings.VEC_FORMAT)
    text = "def f():\n    return 1\n"
    current_blob = embeddings.pack_vector(
        np.zeros(embeddings.DIM, dtype=np.float32)
    )
    _seed(temp_index, "good/ok.py", "f", text, current_blob)

    _no_model(monkeypatch)  # embed would return ones (differs from zeros)
    monkeypatch.setattr(
        embeddings, "enumerate_sources",
        lambda: ([("code", "good/ok.py", "f", text)], False),
    )

    assert embeddings.refresh() == 0

    assert _embedding_of(temp_index, "good/ok.py", "f") == current_blob, \
        "unchanged row in a marked index must not be re-embedded"
    assert _user_version(temp_index) == embeddings.VEC_FORMAT


@pytest.fixture()
def unreadable_source_tree(tmp_path, monkeypatch):
    (tmp_path / "good").mkdir()
    (tmp_path / "good" / "ok.py").write_text("def f():\n    return 1\n")
    (tmp_path / "bad").mkdir()
    monkeypatch.setattr(embeddings, "BASE", tmp_path)
    monkeypatch.setattr(embeddings, "INDEXED_SOURCE_DIRS", ("bad/", "good/"))
    monkeypatch.setattr(embeddings, "INDEXED_ROOT_GLOBS", ())
    monkeypatch.setattr(embeddings, "_excluded", lambda p: False)
    orig_rglob = Path.rglob

    def fake_rglob(self, pattern):
        if self.name == "bad":
            raise PermissionError(13, "Permission denied", str(self))
        return orig_rglob(self, pattern)

    monkeypatch.setattr(Path, "rglob", fake_rglob)
    _no_model(monkeypatch)
    return tmp_path


def test_stale_format_incomplete_defers(temp_index, unreadable_source_tree):
    """Composition with the incomplete-enumeration fix: when the index is
    stale-format AND enumeration is incomplete, the forced rebuild is
    deferred — rows are kept and the marker is NOT stamped, so a later
    clean refresh still performs the rebuild.
    """
    _seed(temp_index, "bad/old.py", "old_fn", "x", b"OLD-NATIVE-BYTES")
    assert _user_version(temp_index) == 0

    assert embeddings.refresh() == 0

    assert _row_exists(temp_index, "bad/old.py", "old_fn"), \
        "stale row must not be wiped when it cannot be re-embedded"
    assert _user_version(temp_index) == 0, \
        "marker must not be stamped on an incomplete run (rebuild deferred)"
