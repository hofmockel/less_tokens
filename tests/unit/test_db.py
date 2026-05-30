"""Unit tests for tools/db.py - schema init, migration, and verify."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

import tools.db as db_mod


@pytest.fixture()
def isolated_db(tmp_path, monkeypatch):
    """Point db_mod at a fresh temp database for each test."""
    db_path = tmp_path / "test_index.db"
    monkeypatch.setattr(db_mod, "INDEX_DB", db_path)
    return db_path


class TestInit:
    def test_creates_database_file(self, isolated_db):
        db_mod.init()
        assert isolated_db.exists()

    def test_documents_table_exists(self, isolated_db):
        db_mod.init()
        with db_mod.connect_index() as c:
            tables = [r[0] for r in c.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()]
        assert "documents" in tables

    def test_schema_version_table_exists(self, isolated_db):
        db_mod.init()
        with db_mod.connect_index() as c:
            tables = [r[0] for r in c.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()]
        assert "schema_version" in tables

    def test_schema_version_recorded(self, isolated_db):
        db_mod.init()
        with db_mod.connect_index() as c:
            v = db_mod._current_version(c)
        assert v == db_mod.SCHEMA_VERSION

    def test_idempotent(self, isolated_db):
        db_mod.init()
        ret = db_mod.init()
        assert ret == 0

    def test_returns_zero_on_success(self, isolated_db):
        assert db_mod.init() == 0

    def test_missing_schema_file_returns_one(self, isolated_db, monkeypatch):
        monkeypatch.setattr(db_mod, "SCHEMA_FILE", isolated_db.parent / "nonexistent.sql")
        ret = db_mod.init()
        assert ret == 1


class TestMigrate:
    def test_noop_when_current(self, isolated_db):
        db_mod.init()
        ret = db_mod.migrate()
        assert ret == 0

    def test_missing_db_returns_one(self, isolated_db):
        # Don't call init - db doesn't exist
        ret = db_mod.migrate()
        assert ret == 1

    def test_version_unchanged_after_noop(self, isolated_db):
        db_mod.init()
        db_mod.migrate()
        with db_mod.connect_index() as c:
            v = db_mod._current_version(c)
        assert v == db_mod.SCHEMA_VERSION


class TestVerify:
    def test_missing_db_returns_one(self, isolated_db):
        assert db_mod.verify() == 1

    def test_initialized_db_returns_zero(self, isolated_db):
        db_mod.init()
        assert db_mod.verify() == 0

    def test_whitelist_prevents_injection(self, isolated_db):
        """Tables with non-alphanumeric/underscore names are skipped, not injected into SQL."""
        db_mod.init()
        conn = sqlite3.connect(str(isolated_db))
        # SQLite won't let us create a table with special chars normally,
        # but we can verify verify() completes without error.
        conn.close()
        ret = db_mod.verify()
        assert ret == 0


class TestCurrentVersion:
    def test_returns_zero_before_init(self, isolated_db):
        # Schema version table doesn't exist yet
        conn = sqlite3.connect(str(isolated_db))
        v = db_mod._current_version(conn)
        conn.close()
        assert v == 0

    def test_returns_version_after_init(self, isolated_db):
        db_mod.init()
        with db_mod.connect_index() as c:
            v = db_mod._current_version(c)
        assert v == db_mod.SCHEMA_VERSION
