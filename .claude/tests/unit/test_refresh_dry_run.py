"""embeddings.py refresh --dry-run previews changes and writes nothing.

Verifying a config or source change before committing the index meant
running a real refresh (model download, db writes). `refresh --dry-run`
reports add/update/unchanged/delete counts, loads no model, and leaves
index.db byte-identical.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(REPO))
from tools import embeddings  # noqa: E402

_DB = sys.modules[embeddings.connect_index.__module__]


@pytest.fixture()
def fake_sources(monkeypatch):
    monkeypatch.setattr(
        embeddings,
        "enumerate_sources",
        lambda: (
            [
                ("code", "tools/x.py", "f", "new-body"),
                ("code", "tools/x.py", "g", "changed-body"),
                ("code", "tools/y.py", "h", "same-body"),
            ],
            False,
        ),
    )


def _seed(dbp: Path) -> None:
    conn = sqlite3.connect(dbp)
    conn.execute(
        "CREATE TABLE documents (id INTEGER PRIMARY KEY, source_type TEXT, "
        "source_path TEXT, source_key TEXT, text TEXT, content_hash TEXT, "
        "embedding BLOB, embedding_model TEXT, updated_at TEXT)"
    )
    conn.executemany(
        "INSERT INTO documents (source_path, source_key, content_hash) "
        "VALUES (?, ?, ?)",
        [
            ("tools/x.py", "g", "OLD_HASH"),  # update (hash differs)
            ("tools/y.py", "h", embeddings._sha256("same-body")),  # unchanged
            ("tools/gone.py", "z", "h"),  # delete (not enumerated)
        ],
    )
    conn.commit()
    conn.close()


def test_dry_run_reports_counts_and_writes_nothing(
    fake_sources, tmp_path, monkeypatch, capsys
):
    dbp = tmp_path / "index.db"
    _seed(dbp)

    def _rows():
        c = sqlite3.connect(dbp)
        try:
            return sorted(
                c.execute(
                    "SELECT source_path, source_key, content_hash FROM documents"
                ).fetchall()
            )
        finally:
            c.close()

    before = _rows()

    def _boom():
        raise AssertionError("dry-run must not load the embedding model")

    monkeypatch.setattr(embeddings, "_get_model", _boom)
    monkeypatch.setattr(_DB, "INDEX_DB", dbp)

    rc = embeddings.refresh(dry_run=True)

    assert rc == 0
    out = capsys.readouterr().out
    assert "DRY RUN" in out
    assert "add: 1" in out
    assert "update: 1" in out
    assert "unchanged: 1" in out
    assert "delete: 1" in out
    assert _rows() == before


def test_dry_run_full_reports_all_existing_as_delete(
    fake_sources, tmp_path, monkeypatch, capsys
):
    dbp = tmp_path / "index.db"
    _seed(dbp)
    monkeypatch.setattr(_DB, "INDEX_DB", dbp)

    rc = embeddings.refresh(full=True, dry_run=True)

    assert rc == 0
    assert "delete: 3" in capsys.readouterr().out


def test_dry_run_no_index_file_treats_all_as_add(
    fake_sources, tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(_DB, "INDEX_DB", tmp_path / "absent.db")

    rc = embeddings.refresh(dry_run=True)

    assert rc == 0
    out = capsys.readouterr().out
    assert "add: 3" in out
    assert not (tmp_path / "absent.db").exists()
