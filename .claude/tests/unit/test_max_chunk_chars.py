"""MAX_CHUNK_CHARS splits oversized chunks at paragraph/line boundaries.

Without a size limit, a large markdown section or a long function body
becomes a single giant chunk. MAX_CHUNK_CHARS in search_config caps chunk
size so results fit a model's context window without overwhelming it.
"""
from __future__ import annotations

import sys

from tests.conftest import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / ".claude" / "tools"))
import embeddings  # noqa: E402
import search_config  # noqa: E402


def _para(n: int) -> str:
    """Return a paragraph of exactly n 'x' chars (no newlines)."""
    return "x" * n


def test_markdown_oversized_chunk_is_split(tmp_path, monkeypatch):
    """chunk_markdown splits a section body exceeding MAX_CHUNK_CHARS."""
    monkeypatch.setattr(search_config, "MAX_CHUNK_CHARS", 100)
    # Build a section whose body is ~300 chars across three paragraphs
    body = "\n\n".join([_para(90), _para(90), _para(90)])
    md = tmp_path / "doc.md"
    md.write_text(f"## Big Section\n\n{body}\n")

    chunks = dict(embeddings.chunk_markdown(md))

    # Original key present; at least one continuation key
    assert "Big Section" in chunks
    assert any(k.startswith("Big Section_") for k in chunks), (
        f"Expected split sub-chunks, got keys: {list(chunks)}"
    )
    # Every piece is within the limit
    for k, v in chunks.items():
        assert len(v) <= 100, f"Chunk {k!r} exceeds limit: {len(v)}"


def test_markdown_small_chunk_not_split(tmp_path, monkeypatch):
    """chunk_markdown leaves short sections intact."""
    monkeypatch.setattr(search_config, "MAX_CHUNK_CHARS", 500)
    md = tmp_path / "small.md"
    md.write_text("## Intro\n\nShort body.\n\n## End\n\nAlso short.\n")

    chunks = dict(embeddings.chunk_markdown(md))
    assert set(chunks) == {"Intro", "End"}


def test_zero_disables_splitting(tmp_path, monkeypatch):
    """MAX_CHUNK_CHARS=0 disables size capping entirely."""
    monkeypatch.setattr(search_config, "MAX_CHUNK_CHARS", 0)
    big = "y" * 5000
    md = tmp_path / "huge.md"
    md.write_text(f"## Huge\n\n{big}\n")

    chunks = dict(embeddings.chunk_markdown(md))
    assert "Huge" in chunks
    assert len(chunks["Huge"]) == len("## Huge\n\n") + 5000  # heading + separator + body
