# Codex hook payload fixtures

These are sanitized payloads captured from live `PreToolUse:Bash` calls on 2026-07-19.
The runs used the published event-keyed inline hook configuration and hook-trust bypass in an
isolated temporary repository. Each release captured a `pwd` Bash call and an `apply_patch` local
function call.

- `0.142.3/pre-tool-use-bash.json`: standalone `codex-cli 0.142.3`, model `gpt-5.5`.
- `0.144.5/pre-tool-use-bash.json`: ChatGPT desktop-bundled `codex-cli 0.144.5`, model
  `gpt-5.6-sol`.
- Each release directory also contains `pre-tool-use-apply-patch.json` from its non-Bash probe.

Session, turn, tool-use, and filesystem identifiers are replaced with stable placeholders. The
field set and the release-specific tool-use ID prefix are retained.

Schema provenance: [`rust-v0.142.3`](https://github.com/openai/codex/tree/rust-v0.142.3/codex-rs/hooks/schema/generated) and [`rust-v0.144.5`](https://github.com/openai/codex/tree/rust-v0.144.5/codex-rs/hooks/schema/generated).
