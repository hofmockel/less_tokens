# `edit_verification` — Claude bounded live capture

Captured 2026-07-22. Hooks invoked directly with real stdin payloads matching the installed
Claude Code `PostToolUse`/`PreToolUse` schema — a live interactive Claude Code session inside
this repo was not spawned this run (this session is rooted in a different project); see
`indexed_whole_file_read/codex/README.md` for the same-precedent method used earlier in this
matrix.

## Method

1. `sample.py` (this directory) exists on disk. `post-edit-diff.py` was invoked with a
   `PostToolUse:Edit` payload (`post-tool-use-edit.json`) describing an edit to its `greet`
   function (`"Hi, {name}."` -> `"Hello, {name}!"`).
2. Immediately after (real elapsed time, no synthetic clock), `read-after-edit.py` was invoked
   with a `PreToolUse:Read` payload (`pre-tool-use-read-blocked.json`) for the same file.

## Results

| Probe | Output | Exit |
| --- | --- | --- |
| `PostToolUse:Edit` | `hookSpecificOutput.additionalContext` containing the real 2-line unified diff (`diff_edit`, no git involved) | 0 |
| `PreToolUse:Read` (10s later) | `read-after-edit: sample.py was edited 10s ago — diff already in context. Skip the re-Read; use the diff or Read with offset+limit if you need a specific slice.` | 2 |

The blocked `Read` prevented the model from re-absorbing `sample.py`'s full 99 bytes after the
diff had already surfaced it. `event_fired: true`, `action_enforced: true`, `basis: measured`
for `edit_verification:claude:2026-07-21`.
