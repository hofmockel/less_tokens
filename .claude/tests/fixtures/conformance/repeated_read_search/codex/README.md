# `repeated_read_search` — Codex bounded live capture

Captured 2026-07-22 against installed `codex-cli 0.144.6` (standalone,
`/opt/homebrew/lib/node_modules/@openai/codex/bin/codex.js`), model `gpt-5.6-sol` per the
release's real hook schema (same field set as
`.claude/tests/fixtures/codex-hooks/0.144.6/pre-tool-use-bash.json`).

## Method

Installed less_tokens (`--agent codex --create-venv`) into a fresh, disposable temporary Git
repository containing one real 1,142-byte `src/example.py` (auto-detected into
`INDEXED_SOURCE_DIRS`). A second, unrelated Codex build (`ChatGPT.app`, 0.145.0) present on this
machine falls outside `install.py`'s verified hook-contract range and would otherwise abort the
install; it was excluded from `install.py`'s own version scan for this run only (the PATH
`codex-cli 0.144.6` — the release actually under test — was untouched and separately verified in
range). `codex exec` itself was not invoked this session, so the installed
`.codex/hooks/context-cache.py` was invoked directly, three times, via its real stdin JSON
contract (same schema CX26 verified live `codex exec` actually delivers to hooks).

`context-cache.py`'s repeated-read gate only records a read on `PostToolUse` (never on
`PreToolUse` — a denied `PreToolUse` call never gets a matching `PostToolUse`, so recording only
after the fact avoids marking a blocked read as served). The correct sequence is therefore
`PreToolUse` (check, allow) → `PostToolUse` (record) → `PreToolUse` (check again, now blocked) —
mirrored here with a real `mcp__filesystem__read_text_file` payload for `src/example.py`.

A fourth probe repeats the same `Bash cat src/example.py` command twice in a row to check whether
Codex's actual default read path (no MCP filesystem server installed) is covered by the same gate.

## Results

| Probe | Input | Output |
| --- | --- | --- |
| `pre-tool-use-mcp-read-first.json` | first `mcp__filesystem__read_text_file` of `src/example.py` | allowed (no `hookSpecificOutput`, exit 0) |
| `post-tool-use-mcp-read-record.json` | same read, `PostToolUse` | recorded into `.less_tokens/state/context-cache.json` (`reads["src/example.py::None::None"]`), exit 0 |
| `pre-tool-use-mcp-read-second.json` | identical read, immediately after | **Blocked**: `{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"context-cache: example.py already in context (call #4, 0s ago) — file unchanged. Skip this Read; content is still valid in context."}}` |
| `pre-tool-use-bash-cat-repeated.json` | `Bash("cat src/example.py")`, sent twice in a row | **Not blocked either time** — allowed, no `hookSpecificOutput`, exit 0 |

The MCP-filesystem-surfaced read gate works exactly as designed when that surface is exercised:
the second identical read never re-entered context, and the blocked read's full 1,142 bytes were
kept out.

The `Bash cat` result is a real, more severe gap than the Claude-side one recorded for this same
workload. On Claude, `Read` is the tool a session actually uses by default, so the gate covers the
primary path and the `Bash` fallback is a secondary escape hatch. On Codex, a default install ships
no `mcp__filesystem__` server (CX25), so `Bash cat`/`head`/`tail`/`sed` *is* the only real read
path a live session exercises — and `context-cache.py` does not cover it: its `load_json_stdin`
call only applies `map_read_or_search` (which recognizes `mcp__filesystem__*` tool names), never
`map_bash_read` (which several sibling hooks — `search-first.py`, `read-guard.py`,
`grep-first-read.py`, `auto-slice.py`, `read-after-edit.py`, `continue-freshness.py` — do use to
recognize `cat`/`head`/`tail`/`sed`). Even if it did, `check_bash`'s own cacheable-command allowlist
(`pwd`, `git status`, `rg`, `pytest`) excludes plain file reads entirely. So for a default Codex
install, this workload's gate never fires on the read path a real session actually takes.

`event_fired: true`, `code_present: true`, `configured: true` (the hook is wired into
`.codex/hooks.json` for both `PreToolUse` and `PostToolUse` on the `mcp__filesystem__.*|Bash`
matcher and does receive every `Bash` call), but `action_enforced: false` for
`repeated_read_search:codex:0.144.6` — the mechanism is proven only for an optional surface
(`mcp__filesystem__*`) that a default install does not have, while the default install's actual
read path is unguarded.

Schema provenance: same as `.claude/tests/fixtures/codex-hooks/README.md`.
