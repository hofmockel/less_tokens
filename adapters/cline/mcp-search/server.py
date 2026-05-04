#!/usr/bin/env python3
"""Minimal MCP stdio server exposing the project's vector search as a Cline tool.

Wraps `tools/search.py:search()` as a single MCP tool named `search`. Cline (or
any MCP client) calls it via the `less-tokens-search` server registration in
`cline_mcp_settings.json`.

Run directly to test:
    python adapters/cline/mcp-search/server.py
The server speaks JSON-RPC on stdin/stdout per the MCP spec.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(REPO / "tools"))

from mcp.server.fastmcp import FastMCP  # noqa: E402

from search import search as _search  # noqa: E402

server = FastMCP("less-tokens-search")


@server.tool()
def search(query: str, k: int = 3, source_type: str | None = None) -> list[dict]:
    """Semantic search over the project's indexed sources.

    Returns the top-k chunks ranked by cosine similarity. Use this *before*
    reading indexed files — typically 5–10× fewer tokens than a full read.

    Args:
        query: natural-language description of what you're looking for
        k: number of chunks to return (default 3)
        source_type: optional filter — one of: doc, code, journal, changelog, note
    """
    return _search(query, k=k, source_type=source_type)


if __name__ == "__main__":
    server.run()
