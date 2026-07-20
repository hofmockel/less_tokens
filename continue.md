# Continue: less_tokens

> **Next focus:** Finish CX27's native Codex `PreToolUse` decisions, safe read rewrites, telemetry, and parity tests.

## Current state
Branch `codex/cx27-native-pretool` contains an intentional WIP handoff commit and should have a clean
working tree. CX27 remains in `BACKLOG.md`; do not close it until all acceptance evidence passes.

## What happened

- Verified the current official Codex contract at `https://learn.chatgpt.com/docs/hooks#pretooluse`:
  structured deny uses `permissionDecision: "deny"`; rewrites use `"allow"` plus `updatedInput`.
- Added native response helpers in `agents/codex/hooks/_codex_runtime.py` and migrated budget observer,
  search-first, read guard, auto-slice, grep-first, context-cache, listing guard, and continue-freshness.
- Auto-slice now rewrites safe whole-file Bash `cat` calls to the exact search-derived `sed` range;
  filesystem MCP reads deny when their tool schema cannot express an exact offset.
- Began converting `.claude/tests/unit/test_codex_hooks.py` from exit-code assertions to semantic JSON.

## Open work

Finish the remaining Codex hook assertions (grep-first, listing guard, context cache, search-first),
then update `test_codex_event_contract.py` to require native structured outcomes. Add measured input
character/token telemetry without retry double-counting, document unsupported surfaces, run equivalent
Claude `PreToolUse` fixtures, execute focused/full tests, and only then update backlog/changelog.

## Suggested skills

- `$less-tokens` — targeted symbol lookup and final diff inspection.
- `$openai-docs` — re-check the live Codex hook contract if response-shape questions arise.

## Start here

Run `.claude/.venv-tokens/bin/python -m pytest -q .claude/tests/unit/test_codex_hooks.py`, then migrate
each remaining legacy `code == 2` assertion for the eight CX27 hooks to `deny_reason` or `allowed_input`.

---
_Last updated at HEAD `4993e26` on 2026-07-19._
