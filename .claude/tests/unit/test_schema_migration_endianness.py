"""Regression: upgrading a pre-endianness-fix index.db must invalidate the
stale vectors instead of silently misreading them.

Schema v1 stored embeddings in host-native byte order. After the little-endian
fix, `search.py` always decodes `<f4`, so a v1 index built on a big-endian
host scores silently wrong for every row a content-hash-matched `refresh()`
skips. The fix bumps `SCHEMA_VERSION` to 2 and makes `db.migrate()` drop the
`documents` rows when crossing the v1->v2 boundary, and `embeddings.refresh()`
calls `ensure_current_schema()` at startup so the one-time invalidation fires
on the normal upgrade path (install --build / manual refresh / index-refresh
hook) without a manual `db.py migrate`.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(REPO))
from tools import embeddings  # noqa: E402

# embeddings.py imports db's helpers with tools/ on sys.path; patch INDEX_DB
# on the exact module instance embeddings uses.
_DB = sys.modules[embeddings.connect_index.__module__]


def _make_v1_index(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        "CREATE TABLE schema_version "
        "(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);"
        "CREATE TABLE documents ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " source_type TEXT NOT NULL, source_path TEXT NOT NULL,"
        " source_key TEXT NOT NULL, text TEXT NOT NULL,"
        " content_hash TEXT NOT NULL, embedding BLOB NOT NULL,"
        " embedding_model TEXT NOT NULL, updated_at TEXT NOT NULL,"
        " UNIQUE (source_path, source_key));"
    )
    conn.execute(
        "INSERT INTO schema_version (version, applied_at) "
        "VALUES (1, '2026-01-01')"
    )
    conn.execute(
        "INSERT INTO documents (source_type, source_path, source_key, text, "
        "content_hash, embedding, embedding_model, updated_at) "
        "VALUES ('code','a.py','f','t','h',?,'m','2026-01-01')",
        (b"\x00\x01\x02\x03",),
    )
    conn.commit()
    conn.close()


def _insert_row(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        "INSERT INTO documents (source_type, source_path, source_key, text, "
        "content_hash, embedding, embedding_model, updated_at) "
        "VALUES ('code','b.py','g','t','h',?,'m','2026-01-02')",
        (b"\x00\x00\x00\x00",),
    )
    conn.commit()
    conn.close()


def _version(path: Path) -> int:
    conn = sqlite3.connect(path)
    try:
        return conn.execute(
            "SELECT MAX(version) FROM schema_version"
        ).fetchone()[0]
    finally:
        conn.close()


def _doc_count(path: Path) -> int:
    conn = sqlite3.connect(path)
    try:
        return conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    finally:
        conn.close()


def _no_fastembed(monkeypatch):
    def _boom():
        raise RuntimeError("fastembed not installed")

    monkeypatch.setattr(embeddings, "_get_model", _boom)


class TestMigrateInvalidatesV1:
    def test_migrate_v1_to_v2_drops_documents(self, tmp_path, monkeypatch):
        dbp = tmp_path / "index.db"
        _make_v1_index(dbp)
        monkeypatch.setattr(_DB, "INDEX_DB", dbp)
        assert _doc_count(dbp) == 1

        assert _DB.migrate() == 0

        assert _version(dbp) == 2
        assert _doc_count(dbp) == 0  # stale native-endian rows invalidated

    def test_migrate_is_noop_once_at_v2(self, tmp_path, monkeypatch):
        dbp = tmp_path / "index.db"
        _make_v1_index(dbp)
        monkeypatch.setattr(_DB, "INDEX_DB", dbp)
        _DB.migrate()  # v1 -> v2, clears the stale row
        _insert_row(dbp)  # as if a fresh v2 refresh repopulated

        assert _DB.migrate() == 0  # already v2 -> no-op
        assert _version(dbp) == 2
        assert _doc_count(dbp) == 1  # v2 row preserved, not re-dropped


class TestEnsureCurrentSchema:
    def test_missing_db_initializes_at_v2(self, tmp_path, monkeypatch):
        dbp = tmp_path / "index.db"
        monkeypatch.setattr(_DB, "INDEX_DB", dbp)
        assert not dbp.exists()

        assert _DB.ensure_current_schema() == 0

        assert dbp.exists()
        assert _version(dbp) == 2
        assert _doc_count(dbp) == 0

    def test_existing_v1_db_is_migrated(self, tmp_path, monkeypatch):
        dbp = tmp_path / "index.db"
        _make_v1_index(dbp)
        monkeypatch.setattr(_DB, "INDEX_DB", dbp)

        assert _DB.ensure_current_schema() == 0

        assert _version(dbp) == 2
        assert _doc_count(dbp) == 0


class TestRefreshAutoMigrates:
    def test_refresh_invalidates_v1_before_model_check(
        self, tmp_path, monkeypatch
    ):
        """refresh() must call ensure_current_schema() at the very top, so a
        v1 index is invalidated even where fastembed is unavailable (refresh()
        returns early after the model check).
        """
        dbp = tmp_path / "index.db"
        _make_v1_index(dbp)
        monkeypatch.setattr(_DB, "INDEX_DB", dbp)
        _no_fastembed(monkeypatch)

        assert embeddings.refresh() == 0
        assert _version(dbp) == 2
        assert _doc_count(dbp) == 0
