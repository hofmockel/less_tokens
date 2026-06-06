"""Regression: search.py --source-type choices must track the index, not a
static list.

`--source-type` used `choices=SOURCE_TYPES`, a hardcoded list in
search_config.py. That list and the `documents.source_type` column are two
unsynchronised sources of truth: it advertises values the indexer never
produces (`journal`, `note` → always zero rows) and rejects any value a
different/older index legitimately contains. The fix derives the choices
from `SELECT DISTINCT source_type FROM documents` at runtime, falling back
to unconstrained (None) when the index is unavailable.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(REPO))
from tools import search  # noqa: E402

# search.py imports `connect_index` from the top-level `db` module (tools/ is
# put on sys.path inside search.py); patch INDEX_DB on that exact module.
_DB = sys.modules[search.connect_index.__module__]


def _make_index(path: Path, source_types: list[str]) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE documents (id INTEGER PRIMARY KEY, source_type TEXT NOT NULL, "
        "source_path TEXT, source_key TEXT, text TEXT, embedding BLOB)"
    )
    conn.executemany(
        "INSERT INTO documents (source_type, source_path, source_key, text, embedding) "
        "VALUES (?, ?, ?, ?, ?)",
        [(st, f"p/{st}.x", "k", "t", b"") for st in source_types],
    )
    conn.commit()
    conn.close()


@pytest.fixture()
def index_db(tmp_path, monkeypatch):
    dbp = tmp_path / "index.db"
    # 'legacy' is deliberately NOT in search_config.SOURCE_TYPES.
    _make_index(dbp, ["code", "doc", "changelog", "legacy", "code"])
    monkeypatch.setattr(_DB, "INDEX_DB", dbp)
    return dbp


class TestSourceTypeChoices:
    def test_returns_distinct_sorted_from_db(self, index_db):
        assert search._source_type_choices() == ["changelog", "code", "doc", "legacy"]

    def test_includes_value_absent_from_static_list(self, index_db):
        from tools.search_config import SOURCE_TYPES

        choices = search._source_type_choices()
        assert "legacy" in choices
        assert "legacy" not in SOURCE_TYPES  # the drift the bug is about

    def test_none_when_index_unavailable(self, tmp_path, monkeypatch):
        # Empty/uninitialised db → no `documents` table → unconstrained.
        empty = tmp_path / "empty.db"
        sqlite3.connect(empty).close()
        monkeypatch.setattr(_DB, "INDEX_DB", empty)
        assert search._source_type_choices() is None


class TestArgparseTracksIndex:
    def test_accepts_db_value_that_static_list_rejected(
        self, index_db, tmp_path, monkeypatch
    ):
        """End-to-end: `--source-type legacy` is valid because it's in the
        index. Pre-fix, argparse `choices=SOURCE_TYPES` SystemExit(2)'d on it.
        """
        monkeypatch.setattr(search, "STATE_DIR", tmp_path / "state")
        monkeypatch.setattr(search, "search", lambda *a, **k: [])
        monkeypatch.setattr(
            sys, "argv", ["search.py", "q", "--source-type", "legacy"]
        )
        assert search.main() == 0
