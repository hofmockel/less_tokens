# `indexed_whole_file_read` — Claude bounded live capture

Captured 2026-07-21 in this dogfooded repo's own live Claude Code session (not a synthetic
scratch repo — the real `.claude/hooks/grep-first-read.py` install, real transcript).

## Method

Attempted a whole-file `Read` (no `offset`/`limit`) of `agents/common/hooks/hook_manifest.py`,
a 389-line / 14,546-byte indexed source file, from a real working session. No search had been
run against that file first.

## Results

| Probe | Input | Output |
| --- | --- | --- |
| Initial `Read(hook_manifest.py)` | whole-file read, no offset/limit | Blocked: `Grep-first: Grep-first gate (S13): hook_manifest.py is 389 lines (threshold 150).` plus the suggested `symbols.py`/`search.py` commands and a `Read(offset=<line>, limit=<n>)` retry shape |
| Follow-up `Read(hook_manifest.py, offset=1, limit=60)` | targeted slice | Allowed; only lines 1-60 delivered |

The blocked call never reached the model with file content; the allowed retry delivered roughly
60/389 lines (~15%) of the file. `model_visible_bytes_removed` in `matrix.json` is a proportional
estimate (14,546 × (1 − 60/389) ≈ 12,302 bytes), not a byte-exact diff, because the slice's exact
serialized size (including line-number prefixes) was not separately captured.

`event_fired: true`, `action_enforced: true`, `basis: measured` for
`indexed_whole_file_read:claude:2026-07-21`.
