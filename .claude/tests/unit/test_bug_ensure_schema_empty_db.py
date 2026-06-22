"""Bug: search.py creates empty index.db, breaking subsequent migrate().

connect_index() calls sqlite3.connect(INDEX_DB) which creates an empty db file
if it doesn't exist. ensure_current_schema() then sees the file exists, calls
migrate() instead of init(), and migrate()'s INSERT INTO schema_version crashes
because the table is absent.

Fix: ensure_current_schema() must call init() when _current_version() == 0
(no schema present), not just when the file is absent.
"""
from __future__ import annotations

import importlib
import importlib.util
import sqlite3
import sys
from pathlib import Path

from tests.conftest import REPO_ROOT


def _load_db_mod(index_db: Path):
    """Load db.py with INDEX_DB monkeypatched to a tmp path."""
    tools_dir = REPO_ROOT / ".claude" / "tools"
    if str(tools_dir) not in sys.path:
        sys.path.insert(0, str(tools_dir))

    spec = importlib.util.spec_from_file_location("db_tmp", tools_dir / "db.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.INDEX_DB = index_db  # patch after exec; functions look up globals at call time
    return mod


def test_ensure_current_schema_on_empty_db_file(tmp_path):
    """ensure_current_schema() must not crash when index.db exists but is empty.

    Reproduces: connect_index() creates a bare sqlite3 file (no tables);
    ensure_current_schema() must call init() rather than migrate().
    """
    index_db = tmp_path / "index.db"

    # Simulate the side-effect of connect_index() being called first:
    # sqlite3.connect creates the file but writes no tables.
    conn = sqlite3.connect(index_db)
    conn.close()
    assert index_db.exists()

    mod = _load_db_mod(index_db)
    mod.INDEX_DB = index_db

    result = mod.ensure_current_schema()
    assert result == 0, "ensure_current_schema() must succeed on an empty db file"

    # Verify the schema was actually created (not just a silent no-op).
    with sqlite3.connect(index_db) as c:
        tables = {
            r[0]
            for r in c.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert "documents" in tables, "init() must create the documents table"
    assert "schema_version" in tables, "init() must create the schema_version table"
