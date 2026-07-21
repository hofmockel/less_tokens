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
- Converted the Codex hook and event-contract suites from exit-code assertions to semantic JSON;
  focused suites pass (`49` and `166` tests) and the full unit suite passes (`1117` tests).

## Open work

Add measured input character/token telemetry without retry double-counting, document unsupported
surfaces, and run equivalent Claude `PreToolUse` fixtures. CX27 now has an in-progress changelog entry;
only close the backlog item after the remaining acceptance evidence is implemented and verified.

## Suggested skills

- `$less-tokens` — targeted symbol lookup and final diff inspection.
- `$openai-docs` — re-check the live Codex hook contract if response-shape questions arise.

## Start here

Trace the current savings/event telemetry from `agents/common/hooks/budget_observer.py` and
`agents/common/savings.py`, then add one correlation-safe measurement for rewritten or denied input.

---
_Last updated at HEAD `74b5e7e` on 2026-07-20._
