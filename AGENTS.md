<!-- less_tokens: begin -->
## Token Discipline

Use targeted context. Prefer `rg`, `rg --files`, semantic search, and file slices over full-file reads.

Search before reading large or indexed files; use symbol lookup for definitions.

Check lockfiles, generated bundles, binaries, and large data files before reading them in full.

Directory navigation: prefer `rg --files` over recursive listings.

Responses: direct findings, exact file:line references, no filler.

Terse mode does not apply to a document/report/proposal the user asked for — see the
`less-tokens` skill for the exemption marker.

For installed commands and AGENTS.md hygiene, use the `less-tokens` skill.
<!-- less_tokens: end -->
