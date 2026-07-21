# `indexed_whole_file_read` — Codex bounded live capture

Captured 2026-07-21 against installed `codex-cli 0.144.6` (standalone, `/opt/homebrew/lib/node_modules/@openai/codex/bin/codex.js`), model `gpt-5.6-sol` per the release's real hook schema (same field set as `.claude/tests/fixtures/codex-hooks/0.144.6/pre-tool-use-bash.json`).

## Method

Installed less_tokens (`--agent codex`) into a fresh, disposable temporary Git repository containing one real ~855-byte `src/example.py` (auto-detected into `INDEXED_SOURCE_DIRS`). `codex exec` itself could not be invoked in this session (sandboxed-execution policy blocked spawning a second autonomous CLI agent), so the installed `.codex/hooks/search-first.py` was invoked directly, twice, via its real stdin JSON contract — the same schema CX26 verified live `codex exec` actually delivers to this hook for a Bash `PreToolUse` call. This proves the shipped hook logic against a real installed venv/tool chain and a real file; it does not independently re-prove that `codex exec` dispatches this exact payload (CX26's live headless runs already established that for `cat`).

## Results

| Probe | Input | Output | `savings.jsonl` |
| --- | --- | --- | --- |
| `pre-tool-use-bash-search-blocked.json` | unsearched `cat src/example.py` | `{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"Search-first rule: src/example.py is indexed.\n  .less_tokens/bin/python .less_tokens/tools/search.py \"<your query>\""}}` | new row: `strategy=search-blocked`, `elided_chars=855` (== exact file byte count), `content_kind=source_file` |
| `pre-tool-use-bash-search-recent.json` (same command, after touching `.less_tokens/state/last-search`) | unchanged | empty stdout, exit 0 (native allow — no `hookSpecificOutput`) | no new row |

`event_fired: true`, `action_enforced: true`, `basis: measured` for `indexed_whole_file_read:codex:0.144.6`.

Schema provenance: same as `.claude/tests/fixtures/codex-hooks/README.md`.
