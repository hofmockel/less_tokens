# Search Before Read — MANDATORY

Before reading any file under the project's indexed directories, call the
`search` MCP tool from the `less-tokens-search` server with a natural-language
query. The tool returns the top-k most relevant chunks, typically 5–10× fewer
tokens than reading the full file.

Use `read_file` directly only when:

- The search returned no relevant chunks for the query, or
- You need to *edit* the file (search to satisfy the gate, then read + edit), or
- The index is unavailable (search returns an error).

The MCP tool signature is:

    search(query: str, k: int = 3, source_type: str | None = None) -> list[chunks]

Each chunk has: `score`, `source_type`, `source_path`, `source_key`, `text`.

Indexed sources are configured in `tools/search_config.py` under
`INDEXED_SOURCE_DIRS` and `INDEXED_ROOT_GLOBS`. Default scope: `tools/`,
`schema/`, and root-level `*.md`.
