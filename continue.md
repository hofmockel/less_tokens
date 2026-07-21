# Continue: less_tokens

> **Next focus:** Start CX28's release-matched Codex tool-result replacement research.

## Current state

The worktree is on `codex/cx27-telemetry`, based on `origin/main` at `5087b59` and
dirty with the completed CX27 telemetry, tests, documentation, changelog/backlog closeout,
and this handoff. HEAD `187c54d` contains the earlier handoff-only commit.

## What happened

- PR #95 merged native Codex `PreToolUse` structured allow/deny decisions and safe Bash
  `updatedInput` rewrites for CX27.
- Eight guard wrappers now use the structured contract; focused suites (`49` and `166`
  tests) and the full unit suite (`1117` tests) passed before merge.
- PR #96's conflict was resolved by keeping the canonical backlog from `main`; it merged as
  `5087b59`.
- Budget events now use native invocation IDs or stable fallbacks, record canonical input
  characters/estimated tokens once, and atomically deduplicate retries across candidates.
- Shared Codex/Claude `PreToolUse` fixtures pass; the full unit suite is `1120 passed`.
- CX27 moved to `[Unreleased]` and was removed from `BACKLOG.md`; CX28 is now Ready now.

## Open work

CX27 is complete. Continue with the canonical `BACKLOG.md` Ready now table, beginning with CX28.

## Suggested skills

- `less-tokens` for targeted exploration.
- `openai-docs` if the current Codex hook contract needs verification.
- `continue` when handing off again.

## Start here

Verify the current Codex `PostToolUse` result contract and existing live fixtures before
designing CX28's bounded replacement envelope.

_Last updated at HEAD `187c54d` on 2026-07-20._
