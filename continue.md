# Continue: less_tokens

> **Next focus:** Finish the CX19 branch/commit handoff, then take HS1 from `BACKLOG.md`.

## Current state
`main` is at `1f59a6b`, ahead of `origin/main` by 1 and behind by 2. The working tree is dirty with
the uncommitted CX19 implementation in `.claude/tests/unit/test_codex_event_contract.py`, plus
required `BACKLOG.md`, `CHANGELOG.md`, and this handoff update. Do not discard the local commit or
these changes when reconciling with remote. Branch protection requires the established branch + PR
workflow.

## What happened
- CX19 now expands each installed Codex matcher into named semantic scenarios with exact exit-code
  and block-message assertions.
- All six confirmed PreToolUse gates cover state-driven block/allow behavior for filesystem MCP and
  Bash reads, plus error-shaped responses; unknown MCP tools fail open and absent Stop wiring is
  guarded explicitly.
- Verification passed: targeted contract suite (99), full unit suite (1045), and Codex parity audit
  (`Problems: none`; required running outside the sandbox's read-only `.codex` override).
- CX19 was removed from `BACKLOG.md` and cited under `[Unreleased]` in `CHANGELOG.md`.

## Open work
No CX19 implementation work remains. Preserve/review the dirty diff and publish it through a branch
and PR when requested. The next canonical backlog item is HS1, the hybrid retrieval benchmark.

## Suggested skills
- `less-tokens` — targeted codebase exploration for HS1.

## Start here
Run `git diff --check` and the targeted CX19 test, then preserve these changes on a `codex/` branch
before reconciling the diverged local `main` with `origin/main`.

---
_Last updated at HEAD `1f59a6b` on 2026-07-19._
