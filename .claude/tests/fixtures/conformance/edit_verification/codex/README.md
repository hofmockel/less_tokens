# `edit_verification` — Codex bounded live capture

Captured 2026-07-22 against installed Codex adapters (`0.144.6` contract). Hooks invoked
directly with real stdin payloads matching the verified schema; `codex exec` itself was not
spawned this session (sandbox policy), same precedent as `indexed_whole_file_read/codex`.

## Method

1. `sample.py` (this directory) was staged with `git add` (not committed) so `git diff HEAD`
   has a real addition to show — `post-edit-diff.py`'s `apply_patch` branch derives its diff
   from `git diff HEAD`, unlike the Claude `Edit` path which diffs the payload's
   `old_string`/`new_string` directly.
2. `.codex/hooks/post-edit-diff.py` was invoked with a real `PostToolUse:apply_patch` payload
   (`post-tool-use-apply-patch.json`, `*** Add File:` patch text) matching the verified 0.144.6
   `tool_input.command` shape.
3. Immediately after, `.codex/hooks/read-after-edit.py` was invoked with a `PreToolUse:Bash`
   payload (`pre-tool-use-bash-cat-blocked.json`, `cat <path>`) for the same file — the file was
   then unstaged (`git reset`) to leave the tree as found.

## Results

| Probe | Output | Exit |
| --- | --- | --- |
| `PostToolUse:apply_patch` | `hookSpecificOutput.additionalContext` with a compact hunk summary (`1 hunk(s), +6 -0`) plus the real `git diff --git a/... b/...` full diff | 0 |
| `PreToolUse:Bash cat` (11s later) | `read-after-edit: sample.py was edited 11s ago — diff already in context. Skip the whole-file reread; use the diff or read a targeted slice.` | 2 |

This is a materially different (better) result than `repeated_read_search:codex`'s finding:
`read-after-edit.py`'s Codex adapter *does* call `map_bash_read` (unlike `context-cache.py`), so
a plain `Bash cat` of a just-edited file is genuinely blocked, not just an unused
`mcp__filesystem__` surface. `event_fired: true`, `action_enforced: true`, `basis: measured` for
`edit_verification:codex:0.144.6`.
