# Codex hook payload fixtures

These are sanitized payloads captured from live Codex hook calls on 2026-07-19. The runs used the
published event-keyed inline hook configuration and hook-trust bypass in an isolated temporary
repository.

- `0.142.3/pre-tool-use-bash.json`: standalone `codex-cli 0.142.3`, model `gpt-5.5`.
- `0.144.5/pre-tool-use-bash.json`: ChatGPT desktop-bundled `codex-cli 0.144.5`, model
  `gpt-5.6-sol`.
- Each release directory also contains `pre-tool-use-apply-patch.json` from its non-Bash probe.
- `0.144.6/`: standalone `codex-cli 0.144.6`, model `gpt-5.6-sol`. This release adds live
  `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, and `Stop` payloads across Bash,
  `apply_patch`, and `update_plan`. The failed Bash probe (`false`) emitted an empty string in
  `tool_response` with no separate error field.

Session, turn, tool-use, and filesystem identifiers are replaced with stable placeholders. The
field set and the release-specific tool-use ID prefix are retained.

## Surface coverage

| Surface | Live coverage | Notes |
| --- | --- | --- |
| Standalone CLI | `0.142.3`, `0.144.6` | Current lifecycle/local-tool matrix is from `0.144.6`. |
| Codex desktop app | bundled CLI `0.144.5` | `PreToolUse` Bash and `apply_patch` only. |
| IDE extension | Not captured | Keep separate; do not infer from CLI fixtures. |
| Hosted/cloud tools | Not applicable to local tool hooks | Published docs say hosted tools do not enter this hook path. |

`PermissionRequest` did not fire in the non-interactive read-only probe. `PreCompact`,
`PostCompact`, `SubagentStart`, and `SubagentStop` remain schema-documented but are not represented
as live fixtures here.

Schema provenance: [`rust-v0.142.3`](https://github.com/openai/codex/tree/rust-v0.142.3/codex-rs/hooks/schema/generated), [`rust-v0.144.5`](https://github.com/openai/codex/tree/rust-v0.144.5/codex-rs/hooks/schema/generated), and the current official Codex hook manual captured alongside the `0.144.6` probe.
