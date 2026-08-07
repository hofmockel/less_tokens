"""Regression: an incomplete source enumeration must not delete
previously-indexed rows.

Once `enumerate_sources()` learned to skip an unreadable subtree and
continue (f951d61 and its health-path sibling), `refresh()` started
receiving a *partial* source list whenever a directory was transiently
unreadable. Its prune step deletes every existing row whose
`(source_path, source_key)` is not in `seen`, so the unreadable subtree's
still-usable rows were silently deleted — and `refresh --full`, which wipes
the whole table up front, was worse still. The fix has `enumerate_sources()`
report whether enumeration was complete and makes `refresh()` skip both
delete paths when it was not, keeping the stale-but-usable index until a
clean refresh reconciles it.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(REPO))
from tools import embeddings  # noqa: E402

# `connect_index` is imported into embeddings from the top-level `db` module;
# INDEX_DB lives there, so patch it on that exact module object.
_DB = sys.modules[embeddings.connect_index.__module__]


def _seed_row(dbp, source_path, source_key, text="x"):
    c = sqlite3.connect(dbp)
    try:
        c.execute(
            "INSERT INTO documents (source_type, source_path, source_key, "
            "text, content_hash, embedding, embedding_model, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "code",
                source_path,
                source_key,
                text,
                "deadbeef",
                b"\x00\x00\x00\x00",
                embeddings.MODEL,
                "2026-01-01T00:00:00+00:00",
            ),
        )
        c.commit()
    finally:
        c.close()


def _row_exists(dbp, source_path, source_key) -> bool:
    c = sqlite3.connect(dbp)
    try:
        return (
            c.execute(
                "SELECT 1 FROM documents WHERE source_path=? AND source_key=?",
                (source_path, source_key),
            ).fetchone()
            is not None
        )
    finally:
        c.close()


@pytest.fixture()
def temp_index(tmp_path, monkeypatch):
    """A real schema/index.sql database in a temp dir."""
    dbp = tmp_path / "index.db"
    monkeypatch.setattr(_DB, "INDEX_DB", dbp)
    _DB.init()
    return dbp


def _patch_no_model(monkeypatch):
    """refresh() bails early if fastembed is unavailable; make the model a
    no-op and embed deterministic so the DB logic runs without fastembed.
    """
    monkeypatch.setattr(embeddings, "_get_model", lambda: None)
    monkeypatch.setattr(
        embeddings,
        "embed",
        lambda texts, *a, **k: np.zeros((len(texts), embeddings.DIM), dtype=np.float32),
    )


@pytest.fixture()
def unreadable_source_tree(tmp_path, monkeypatch):
    """Fake repo BASE: one readable dir ('good') and one whose rglob raises
    PermissionError ('bad'), mirroring the perm-fix fixtures.
    """
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
    _patch_no_model(monkeypatch)
    return tmp_path


def test_enumerate_sources_reports_incomplete(unreadable_source_tree):
    sources, incomplete = embeddings.enumerate_sources()
    assert incomplete is True
    assert any(row[1] == "good/ok.py" for row in sources), (
        "readable source must still be enumerated"
    )


def test_enumerate_sources_complete_when_all_readable(tmp_path, monkeypatch):
    (tmp_path / "good").mkdir()
    (tmp_path / "good" / "ok.py").write_text("def f():\n    return 1\n")
    monkeypatch.setattr(embeddings, "BASE", tmp_path)
    monkeypatch.setattr(embeddings, "INDEXED_SOURCE_DIRS", ("good/",))
    monkeypatch.setattr(embeddings, "INDEXED_ROOT_GLOBS", ())
    monkeypatch.setattr(embeddings, "_excluded", lambda p: False)

    sources, incomplete = embeddings.enumerate_sources()
    assert incomplete is False
    assert any(row[1] == "good/ok.py" for row in sources)


def test_incremental_refresh_keeps_rows_when_incomplete(
    temp_index, unreadable_source_tree
):
    _seed_row(temp_index, "bad/old.py", "old_fn")

    assert embeddings.refresh() == 0
    assert _row_exists(temp_index, "bad/old.py", "old_fn"), (
        "row under the unreadable subtree must survive an incomplete refresh"
    )


def test_full_refresh_does_not_wipe_when_incomplete(temp_index, unreadable_source_tree):
    _seed_row(temp_index, "bad/old.py", "old_fn")

    assert embeddings.refresh(full=True) == 0
    assert _row_exists(temp_index, "bad/old.py", "old_fn"), (
        "refresh --full must not wipe rows when enumeration is incomplete"
    )


def test_complete_refresh_still_prunes_orphans(temp_index, tmp_path, monkeypatch):
    """Guard: when enumeration IS complete, a row whose file is gone is
    still pruned — the fix must not over-suppress normal deletion.
    """
    (tmp_path / "good").mkdir()
    (tmp_path / "good" / "ok.py").write_text("def f():\n    return 1\n")
    monkeypatch.setattr(embeddings, "BASE", tmp_path)
    monkeypatch.setattr(embeddings, "INDEXED_SOURCE_DIRS", ("good/",))
    monkeypatch.setattr(embeddings, "INDEXED_ROOT_GLOBS", ())
    monkeypatch.setattr(embeddings, "_excluded", lambda p: False)
    _patch_no_model(monkeypatch)

    _seed_row(temp_index, "good/gone.py", "stale_fn")

    assert embeddings.refresh() == 0
    assert not _row_exists(temp_index, "good/gone.py", "stale_fn"), (
        "orphan row must still be pruned on a complete refresh"
    )
