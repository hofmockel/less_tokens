# Continue: less_tokens

> **Next focus:** Finish CX19's live lifecycle coverage without overstating unsupported surfaces.

## Current state
Branch `codex/cx19-contract-matrix` is one commit ahead of `origin/main` at `2ea6442`. The committed
CX19 runtime, tests, fixture documentation, and `0.144.6` fixture matrix are committed. The working
tree contains only this refreshed handoff and the bounded live-capture plan added to the fixture
README. `BACKLOG.md` and `CHANGELOG.md` remain unchanged because CX19 is not yet complete.

## What happened
- Upgraded standalone CLI is `codex-cli 0.144.6`.
- Captured sanitized live `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, and
  `Stop` payloads for Bash, `apply_patch`, and `update_plan` in an isolated temporary repository.
- A failed Bash command (`false`) emitted `tool_response: ""` with no separate error field.
- Added release-labeled fixture matrix/sanitization tests and documented CLI/app/IDE/hosted
  coverage separately.
- Fixed schema-drift telemetry so it records bounded field/type metadata but preserves the raw
  payload for normal mapping. Added a no-values/fail-open regression test.
- Committed the live hook contract matrix as `2ea6442` (`test(codex): capture live hook contract
  matrix`).
- Added bounded interactive/manual probe designs for permission, compaction, and subagent lifecycle
  events, including stop rules and authenticity requirements.
- Verification passes: focused contract suite `159 passed`; broader Codex hook suite `263 passed`;
  `git diff --check` is clean.

## Open work
The non-interactive read-only probe did not emit `PermissionRequest`. Live `PreCompact`,
`PostCompact`, `SubagentStart`, and `SubagentStop` fixtures are still absent. Run the documented
bounded probes, add only genuinely emitted fixtures plus assertions, then run the full relevant
suite before closing CX19/updating backlog and changelog.

## Suggested skills
- `less-tokens` — targeted fixture and hook exploration.
- `openai-docs` — verify exact lifecycle triggering and surface limits.

## Start here
Run the bounded interactive `PermissionRequest` probe documented in
`.claude/tests/fixtures/codex-hooks/README.md`; do not synthesize a fixture if no event is emitted.

---
_Last updated at HEAD `2ea6442` on 2026-07-19._
