"""Regression test: connect_index() return annotation should be _ClosingConn, not sqlite3.Connection."""
from __future__ import annotations

import typing

import pytest

import tools.db as db_mod


@pytest.fixture()
def isolated_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test_index.db"
    monkeypatch.setattr(db_mod, "INDEX_DB", db_path)
    return db_path


def test_connect_index_annotation_is_closing_conn():
    """Return annotation must be _ClosingConn; sqlite3.Connection was wrong and misled callers."""
    hints = typing.get_type_hints(db_mod.connect_index)
    assert hints["return"] is db_mod._ClosingConn, (
        f"Expected _ClosingConn but annotation says {hints['return']!r}. "
        "Callers using the return value directly (outside 'with') get AttributeError."
    )


def test_connect_index_direct_use_raises_attribute_error(isolated_db):
    """Using connect_index() without 'with' raises AttributeError on .execute() — demonstrates the contract."""
    db_mod.init()
    conn = db_mod.connect_index()
    with pytest.raises(AttributeError):
        conn.execute("SELECT 1")  # _ClosingConn has no .execute method
