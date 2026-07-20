# Continue: less_tokens

> **Next focus:** Finish CX19's live lifecycle coverage without overstating unsupported surfaces.

## Current state
Branch `codex/cx19-contract-matrix` tracks `origin/main` at `da8e2f7`. The working tree is dirty with
uncommitted CX19 runtime, tests, fixture documentation, new `0.144.6` fixtures, and this handoff.
`BACKLOG.md` and `CHANGELOG.md` remain unchanged because CX19 is not yet complete.

## What happened
- Upgraded standalone CLI is `codex-cli 0.144.6`.
- Captured sanitized live `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, and
  `Stop` payloads for Bash, `apply_patch`, and `update_plan` in an isolated temporary repository.
- A failed Bash command (`false`) emitted `tool_response: ""` with no separate error field.
- Added release-labeled fixture matrix/sanitization tests and documented CLI/app/IDE/hosted
  coverage separately.
- Fixed schema-drift telemetry so it records bounded field/type metadata but preserves the raw
  payload for normal mapping. Added a no-values/fail-open regression test.
- Verification passes: focused contract suite `159 passed`; broader Codex hook suite `263 passed`;
  `git diff --check` is clean.

## Open work
The non-interactive read-only probe did not emit `PermissionRequest`. Live `PreCompact`,
`PostCompact`, `SubagentStart`, and `SubagentStop` fixtures are still absent. Decide how to capture
those paths legitimately, then run the full relevant suite and only then close CX19/update backlog
and changelog.

## Suggested skills
- `less-tokens` — targeted fixture and hook exploration.
- `openai-docs` — verify exact lifecycle triggering and surface limits.

## Start here
Inspect `.claude/tests/fixtures/codex-hooks/README.md`, then design bounded live probes for the four
missing lifecycle events and `PermissionRequest`; do not synthesize them as live fixtures.

---
_Last updated at HEAD `da8e2f7` on 2026-07-19._
