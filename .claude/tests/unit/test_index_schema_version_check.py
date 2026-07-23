"""Regression test: _index_db_at_current_schema must reject v1 indexes."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(REPO))
from install import _INDEX_SCHEMA_VERSION, _index_db_at_current_schema  # noqa: E402
from tools.db import SCHEMA_VERSION  # noqa: E402


def _make_db(tmp_path: Path, version: int) -> Path:
    target = tmp_path / ".claude"
    target.mkdir()
    db = target / "index.db"
    with sqlite3.connect(str(db)) as c:
        c.execute("CREATE TABLE schema_version (version INTEGER, applied_at TEXT)")
        c.execute("INSERT INTO schema_version VALUES (?, ?)", (version, "2024-01-01"))
    return tmp_path


def test_current_version_accepted(tmp_path):
    root = _make_db(tmp_path, _INDEX_SCHEMA_VERSION)
    assert _index_db_at_current_schema(root) is True


def test_installer_schema_version_matches_database_schema():
    assert _INDEX_SCHEMA_VERSION == SCHEMA_VERSION


def test_v1_rejected(tmp_path):
    root = _make_db(tmp_path, 1)
    assert _index_db_at_current_schema(root) is False


def test_missing_db_rejected(tmp_path):
    assert _index_db_at_current_schema(tmp_path) is False


def test_future_version_rejected(tmp_path):
    root = _make_db(tmp_path, _INDEX_SCHEMA_VERSION + 1)
    assert _index_db_at_current_schema(root) is False
