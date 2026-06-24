---
name: less-tokens
description: Token-efficient codebase exploration for Codex. Use to search the codebase, look up a symbol, check a file before reading, or audit AGENTS.md size.
---

## less-tokens — Token-Efficient Codebase Exploration

Shared vector search and guard tools installed in `.less_tokens/`.

### Search before reading

    .less_tokens/bin/python .less_tokens/tools/search.py "query"

Returns the top matching chunks by semantic similarity. Run this before a whole-file Read on any large or indexed file.

### Symbol lookup

    .less_tokens/bin/python .less_tokens/tools/symbols.py SymbolName

Returns exact `file:line` for Python and JS/TS functions, classes, constants, and types. Cheaper than grep for definitions.

### Noise-file guard

    .less_tokens/bin/python .less_tokens/tools/read_guard.py path/to/file

Checks whether the file is a lockfile, generated bundle, binary, or large data file. Returns a recommendation before you commit to reading it in full.

### AGENTS.md audit

    .less_tokens/bin/python .less_tokens/tools/agentsmd_audit.py

Checks AGENTS.md token budget, stale line references, and verbosity. Run before adding new sections.

### Rebuild the index

    .less_tokens/bin/python .less_tokens/tools/embeddings.py refresh

Re-embeds any source files that changed since the last index build.
