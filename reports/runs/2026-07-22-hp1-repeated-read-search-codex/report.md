# HP1 — `repeated_read_search:codex` live capture

**Date:** 2026-07-22
**Backlog item:** HP1 (`BACKLOG.md`)
**Status:** one of HP1's three outstanding cells closed; two new gaps filed (CX31, CX32).

## What happened

Continued HP1 from `reports/runs/2026-07-21-hp1-conformance-matrix/report.md`, which left
`repeated_read_search:codex` as `not_yet_measured`. Before any live call, reading
`agents/codex/hooks/context-cache.py` + `agents/common/hooks/context_cache.py` surfaced a real
asymmetry: the hook's mapper (`map_read_or_search`) only rewrites the opt-in
`mcp__filesystem__read_*` tool shape into a synthetic `Read`; it never calls CX25's
`map_bash_read`, unlike the six hooks CX25's fix list actually named
(`search-first`, `grep-first-read`, `read-guard`, `continue-freshness`, `read-after-edit`,
`auto-slice`). So a default Codex install's real read path — `cat`/`head`/`tail`/`sed -n` over
`Bash` — never reaches `context_cache.py`'s `Read` branch.

Captured three live probes by invoking `context-cache.py` directly with real stdin JSON
(`LESS_TOKENS_STATE_DIR` pointed at a disposable temp dir, `PostToolUse` to record then
`PreToolUse` to check, matching the release-tagged `0.144.6` schema):

1. Repeated `rg <pattern> <file>` over `Bash` — **blocked** (native `permissionDecision: deny`).
2. Repeated `cat <file>` over `Bash` (default-install read path) — **not blocked**, confirming the
   gap found by reading the source.
3. Repeated `mcp__filesystem__read_text_file` (opt-in MCP path) — **blocked**, confirming the
   `Read`-branch logic is correct and only the Bash-path wiring is missing.

Also surfaced: this machine's installed Codex is `0.145.0`, outside `install.py`'s verified
`0.142.3–0.144.6` window (CX26). `install.py --target . --agent codex --dry-run` against a fresh
disposable temp repo correctly refused to wire hooks rather than guessing, so the probes replayed
the `0.144.6` schema directly against the hook script instead of going through a real install —
same "hook invoked directly" method `indexed_whole_file_read:codex` used last session.

## Evidence

- `.claude/tests/fixtures/conformance/repeated_read_search/codex/README.md` — method + results table.
- `.claude/tests/fixtures/conformance/repeated_read_search/codex/0.144.6/*.json` — 6 sanitized
  payloads (Post+Pre for each of the 3 probes).
- `agents/common/conformance/matrix.json`'s `repeated_read_search:codex:0.144.6` cell —
  `action_enforced: false` (the workload's primary case, whole-file read, fails by default; the
  working search-repeat sub-case is documented in `notes`, not folded into the boolean, per HP1's
  no-guessed-numbers / no-overclaiming rule).

## Backlog filed

- **CX31** — wire `map_bash_read` into `context-cache.py` so repeated-read caching works on a
  default Codex install (the actual fix).
- **CX32** — extend/verify the Codex hook-contract window past `0.144.6`, since the installed
  release has moved to `0.145.0` (a verification gap, not a code gap — separate from CX31).

## Verification run this session

- `python .claude/tools/conformance_matrix.py` — regenerated `README.md`/`DOCUMENTATION.md`.
- `pytest .claude/tests/unit/test_conformance_matrix.py` — 6/6 passed.
- `python .claude/tools/label_consistency_gate.py` — ok.
- `python .claude/tools/changelog_gate.py` — skipped (no shipped-code change in this diff; only
  fixtures/docs/backlog/matrix data).
- `python .claude/tools/hook_parity_docs.py --check` — clean.
- `pytest .claude/tests` — 1208/1208 passed.

## Remaining HP1 work

`edit_verification` (both agents) and `verbose_final_response` (both agents) are still
`not_yet_measured` — HP1 stays open in `BACKLOG.md` per the "delete only when actually done" rule.
