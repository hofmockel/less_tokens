"""Regression test: duplication() must return {} (not crash or None) when sections is empty."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "tools"))
import claudemd_audit as audit_mod


def test_duplication_empty_sections_returns_empty_dict():
    """No headed sections: duplication() returns {} not None."""
    sections = []
    mock_conn = MagicMock()
    mock_conn.__enter__ = lambda s: mock_conn
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.execute.return_value.fetchall.return_value = [
        {"source_path": "x.md", "source_key": "k", "embedding": b"\x00" * (384 * 4)}
    ]

    with (
        patch.dict(
            "sys.modules",
            {
                "db": MagicMock(connect_index=MagicMock(return_value=mock_conn)),
                "embeddings": MagicMock(
                    DIM=384, embed=MagicMock(), unpack_vectors=MagicMock()
                ),
                "numpy": __import__("numpy"),
                "search_config": MagicMock(EMBEDDING_MODEL="test-model"),
            },
        ),
    ):
        result = audit_mod.duplication(sections)

    assert result == {}, f"Expected empty dict, got {result!r}"


def test_duplication_sections_without_level_returns_empty_dict():
    """Sections with level=0/None (no headings): duplication() returns {}."""
    sections = [{"level": 0, "title": "root", "body": "some text"}]
    mock_conn = MagicMock()
    mock_conn.__enter__ = lambda s: mock_conn
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.execute.return_value.fetchall.return_value = [
        {"source_path": "x.md", "source_key": "k", "embedding": b"\x00" * (384 * 4)}
    ]

    with (
        patch.dict(
            "sys.modules",
            {
                "db": MagicMock(connect_index=MagicMock(return_value=mock_conn)),
                "embeddings": MagicMock(
                    DIM=384, embed=MagicMock(), unpack_vectors=MagicMock()
                ),
                "numpy": __import__("numpy"),
                "search_config": MagicMock(EMBEDDING_MODEL="test-model"),
            },
        ),
    ):
        result = audit_mod.duplication(sections)

    assert result == {}, f"Expected empty dict, got {result!r}"
