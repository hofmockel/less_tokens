<!-- less_tokens: begin -->
## Token Discipline

Use targeted context. Prefer `rg`, `rg --files`, semantic search, and file slices over full-file reads.

Search before reading large indexed files:

    .less_tokens/bin/python .less_tokens/tools/search.py "query"

Symbol lookup (definition only, no embedding cost):

    .less_tokens/bin/python .less_tokens/tools/symbols.py <SymbolName>

Noise-file check before reading lockfiles, generated bundles, or large data files:

    .less_tokens/bin/python .less_tokens/tools/read_guard.py path/to/file

AGENTS.md hygiene audit:

    .less_tokens/bin/python .less_tokens/tools/agentsmd_audit.py

Directory navigation — prefer `rg --files` over `find . -R` or `ls -R`.

Response budget: direct findings, exact file:line references, no filler.

Terse mode does not apply to a document/report/proposal the user asked for — see the
`less-tokens` skill for the exemption marker.
<!-- less_tokens: end -->
