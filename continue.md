# Continue: less_tokens

> **Next focus:** CX26 (P0, Ready), then complete the expanded CX19 contract matrix.

## Current state
Branch `codex/cx19-semantic-hook-fixtures` is based on current `origin/main` (`15d2823`) and carries
the test-only legacy CX19 baseline. The working tree should be clean after the cherry-pick completes.
CX19 remains open because PR #91 expanded it behind CX26 to cover release-labeled current Codex
contracts, live fixtures, lifecycle events, surfaces, and schema telemetry.

## What happened
- Replaced the legacy contract test's permissive `{0,2}` smoke assertion with named semantic
  block/allow/error scenarios and exact outcomes for six existing read gates.
- Covered filesystem MCP and Bash reads, real state-file shapes, unknown-MCP fail-open behavior, and
  the legacy absence of usable Stop wiring.
- Verification passed before rebasing: targeted suite (99), full unit suite (1045), and Codex parity
  audit (`Problems: none`).
- While preparing the PR, current `origin/main` added CX26–CX30/HP1 and broadened CX19. Conflict
  resolution preserved that roadmap and records this change only as a partial legacy baseline.

## Open work
Finish CX26 first. Then extend CX19 with sanitized, release-labeled live fixtures for every supported
contract and surface; do not infer current Codex behavior from the legacy matrix.

## Suggested skills
- `less-tokens` — targeted exploration.
- `openai-docs` — current official Codex hook contract research for CX26.

## Start here
Read the current CX26/CX19 entries in `BACKLOG.md`, then define the supported Codex release range.

---
_Last updated at HEAD `15d2823` on 2026-07-19._
