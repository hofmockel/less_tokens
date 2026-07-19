# Continue: less_tokens

> **Next focus:** Complete CX19's remaining release-labeled Codex contract matrix.

## Current state
Branch `codex/cx19-semantic-hook-fixtures` is one commit ahead of `origin/main` (`15d2823`). The
working tree is dirty with the completed CX26 implementation plus the earlier committed legacy CX19
baseline. CX19 is now the first Ready item.

## What happened
- CX26 now renders the published event-keyed hook contract, migrates the retired matcher-array form,
  preserves unrelated metadata, and fails before writes on malformed files or runtimes outside
  `0.142.3–0.144.6`.
- Install/check/uninstall/parity audit share the contract parser. Health checks verify
  `[features].hooks` and explicitly defer definition-hash trust review to `/hooks`.
- Added sanitized live Bash and `apply_patch` payloads for standalone `0.142.3` and desktop-bundled
  `0.144.5`. The migrated project hook file blocked an unsearched `cat README.md` on both releases.
- Verification: focused CX26/CX19 suite 202 passed; full unit+integration suite 1147 passed;
  `git diff --check` clean; parity audit `Problems: none` outside the sandbox permission shim.

## Open work
CX19 still needs the remaining supported matcher aliases, MCP/other local tools, error, lifecycle,
unsupported-path, surface-separation, and bounded schema-drift telemetry coverage. Follow
`BACKLOG.md` acceptance criteria; do not infer interactive/app/IDE behavior from headless runs.

## Suggested skills
- `less-tokens` — targeted exploration and fixture lookup.
- `openai-docs` — only when a missing current lifecycle field requires official contract research.

## Start here
Inventory CX19's uncovered matcher/event/surface cells against `.claude/tests/fixtures/codex-hooks/`
and `.claude/tests/unit/test_codex_event_contract.py`, then implement the smallest next complete slice.

---
_Last updated at HEAD `32e689d` on 2026-07-19._
