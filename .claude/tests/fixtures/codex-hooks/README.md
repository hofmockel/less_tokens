# Codex hook payload fixtures

These are sanitized payloads captured from live Codex hook calls on 2026-07-19. The runs used the
published event-keyed inline hook configuration and hook-trust bypass in an isolated temporary
repository.

- `0.142.3/pre-tool-use-bash.json`: standalone `codex-cli 0.142.3`, model `gpt-5.5`.
- `0.144.5/pre-tool-use-bash.json`: ChatGPT desktop-bundled `codex-cli 0.144.5`, model
  `gpt-5.6-sol`.
- Each release directory also contains `pre-tool-use-apply-patch.json` from its non-Bash probe.
- `0.144.6/`: standalone `codex-cli 0.144.6`, model `gpt-5.6-sol`. This release adds live
  `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PermissionRequest`, `PostToolUse`, `PreCompact`,
  `PostCompact`, `SubagentStart`, `SubagentStop`, and `Stop` payloads across Bash, `apply_patch`, and `update_plan`. The failed Bash
  probe (`false`) emitted an empty string in
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

`PermissionRequest` did not fire in the non-interactive read-only probe, but a bounded interactive
approval request emitted it before the decision. Manual compaction emitted an ordered `PreCompact` /
`PostCompact` pair. A standalone read-only subagent emitted one correlated `SubagentStart` /
`SubagentStop` pair with the observed `default` agent type.

## Bounded live capture protocol

Run each probe in a new temporary Git repository with a recorder hook for only the named event and
`--dangerously-bypass-hook-trust`. Keep raw logs outside this repository. A missing event is a probe
result, not a fixture.

| Events | Surface and trigger | Bound and acceptance evidence |
| --- | --- | --- |
| `PermissionRequest` | Interactive CLI with `--ask-for-approval on-request`; ask for one harmless escalated Bash command and deny it at the prompt. | Stop after the first decision or 60 seconds. Accept only a payload emitted before the decision whose matcher/tool is `Bash`. |
| `PreCompact`, `PostCompact` | Interactive CLI; complete one short turn, then invoke manual compaction. | Stop after one compaction or 90 seconds. Require one ordered pair from the same session with the documented `manual` trigger. Capture `auto` separately only if a real automatic compaction occurs. |
| `SubagentStart`, `SubagentStop` | Standalone CLI with the stable `multi_agent` feature enabled; request exactly one read-only subagent that runs `pwd`, returns, and is awaited. | Stop after one child completes or 120 seconds. Require one ordered start/stop pair tied to the parent session and retain the observed subagent type. |

For every accepted payload, record the exact CLI version, model, surface, prompt/action, and
timeout here. Sanitize path and identifier values while preserving field names, field types,
event order, matcher values, and release-specific ID shapes. Add fixture assertions in
`test_codex_event_contract.py` in the same change.

Schema provenance: [`rust-v0.142.3`](https://github.com/openai/codex/tree/rust-v0.142.3/codex-rs/hooks/schema/generated), [`rust-v0.144.5`](https://github.com/openai/codex/tree/rust-v0.144.5/codex-rs/hooks/schema/generated), and the current official Codex hook manual captured alongside the `0.144.6` probe.
