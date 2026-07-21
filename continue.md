# Continue: less_tokens

> **Next focus:** Finish CX27's remaining telemetry, unsupported-surface documentation, and Claude parity evidence.

## Current state

PRs #95 and #96 are merged. The worktree is still on the now-merged
`codex/codex-hook-backlog` branch; this refreshed handoff is the only intended local change.
Fetch `origin/main` and start the next implementation on a fresh `codex/` branch.

## What happened

- PR #95 merged native Codex `PreToolUse` structured allow/deny decisions and safe Bash
  `updatedInput` rewrites for CX27.
- Eight guard wrappers now use the structured contract; focused suites (`49` and `166`
  tests) and the full unit suite (`1117` tests) passed before merge.
- PR #96's conflict was resolved by keeping the canonical backlog from `main`; it merged as
  `5087b59`.

## Open work

- Record measured input characters/tokens without double-counting retries.
- Add live evidence that denied or rewritten oversized reads never place the omitted payload in
  the transcript, while sliced and unrecognized commands preserve behavior.
- Document hosted or specialized surfaces that cannot enforce the native contract.
- Run equivalent Claude `PreToolUse` fixtures and close CX27 only when all remaining acceptance
  evidence is captured in `BACKLOG.md`.

## Suggested skills

- `less-tokens` for targeted exploration.
- `openai-docs` if the current Codex hook contract needs verification.
- `continue` when handing off again.

## Start here

Fetch `origin/main`, create a fresh branch, then trace savings/event telemetry from
`agents/common/hooks/budget_observer.py` and `agents/common/savings.py` before adding
correlation-safe measurement and parity fixtures.

_Last updated at HEAD `0281b00` on 2026-07-20._
