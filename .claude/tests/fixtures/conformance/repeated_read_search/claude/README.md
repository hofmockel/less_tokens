# `repeated_read_search` — Claude bounded live capture

Captured 2026-07-21 in this dogfooded repo's own live Claude Code session.

## Method

Attempted a `Read` of `.claude/tools/hook_parity_docs.py` (120 lines / 3,809 bytes). A prior
process (a concurrently-spawned subagent working in the same repo) had read the same file
roughly three minutes earlier, within `context-cache.py`'s `WINDOW_SECONDS=300` TTL window. The
gate is keyed by absolute file path + mtime on disk, not by which process performed the earlier
read, so this exercises a real cross-process cache hit, not just an intra-session repeat.

## Results

| Probe | Input | Output |
| --- | --- | --- |
| `Read(hook_parity_docs.py)` | full read | Blocked: `context-cache: hook_parity_docs.py already in context (call #13, 3m ago) — file unchanged. Skip this Read; content is still valid in context.` |
| `Bash("cat .../hook_parity_docs.py")` | shell fallback, same file, same turn | Succeeded — full content returned |

The blocked `Read` prevented the full 3,809-byte file from re-entering the model's context. The
`Bash` fallback is an honest enforcement-boundary gap: `context-cache.py` gates the `Read`/`Grep`
tool surface specifically, not raw shell reads, so a determined caller can route around it. That
gap is recorded here rather than hidden.

`event_fired: true`, `action_enforced: true` (for the gated surface only), `basis: measured` for
`repeated_read_search:claude:2026-07-21`.
