# Continue: less_tokens

> **Next focus:** CX19 (P1, Ready, next in `BACKLOG.md` order) — replace synthetic Codex hook smoke
> tests with semantic fixtures.

## Current state
CX25 is shipped: the 6 Codex hooks that only fired on an opt-in `mcp__filesystem__` server
(`search-first`, `read-guard`, `auto-slice`, `grep-first-read`, `read-after-edit`,
`continue-freshness`) now also fire on `cat`/`head`/`tail`/`sed -n` Bash reads via a new
`map_bash_read` mapper. `dev.py unit` (985 passed), `codex_parity_audit.py` (`Problems: none`),
`changelog_gate.py` (ok) all clean. This session's commit is about to land on `main` directly (no
branch/PR — see note below).

## What happened this session
- Merged PR #82 (CX24 fix), synced `main` to `e5582c1`.
- Implemented and shipped **CX25**: see `CHANGELOG.md`'s `[CX25]` entry for the full design
  (recognized Bash read shapes, fail-open boundary, files touched). Caught and fixed a `sed -n
  '12p'` offset-parsing bug (`script.split(",")[0]` on `"12p"` isn't an int) during test-writing.
- Regenerated this repo's own dogfooded install (`install.py --self-refresh --agent codex --yes`)
  and the generated docs tables (`hook_parity_docs.py`) after the matcher change — both needed a
  refresh pass, not just the source edit.
- Added 30 unit cases (`test_codex_bash_read_mapping.py`) plus live-shape subprocess fixtures in
  `test_codex_hooks.py` (including a piped-command fail-open case) satisfying CX25's "add
  live-shape fixture coverage" acceptance criterion.
- `BACKLOG.md` CX25 row/detail bullet removed; `CHANGELOG.md` `[Unreleased]` entry added.
- **Deviation from this repo's established CX19–CX24 pattern**: those shipped via a feature branch
  + PR. This session committed straight to `main` on explicit user instruction ("commit") without
  cutting a branch first — flagging in case that's not the intended convention going forward.

## Open work
See [BACKLOG.md](BACKLOG.md). Next up: **CX19** (P1, Ready) — replace
`test_codex_event_contract.py`'s synthetic any-non-crash-code payloads with real-shape fixtures and
semantic outcome assertions. No longer blocked on CX24 (resolved last session) or CX25 (this
session); CX25's own `test_codex_bash_read_mapping.py`/`test_codex_hooks.py` additions are a partial
head start on CX19's "every supported matcher has a real-shape fixture" requirement for the
Bash-read matchers specifically — CX19 still needs to cover the rest (searches, apply_patch,
Edit/Write, tool errors, unknown MCP tools).

## Suggested skills
- None specific — CX19 is fixture/test-authoring work, not a bugfix/bug-hunt shape.

## Start here
Read `BACKLOG.md`'s CX19 entry in full (acceptance criteria + the live-testing note about
`PostToolUse` non-firing), then start with the Pre-side matchers already confirmed live (per that
note): `mcp__filesystem__.*` and `Bash`.

---
_Last updated at HEAD `e5582c1` (working tree staged, about to commit CX25 directly on `main`) on
2026-07-18._
