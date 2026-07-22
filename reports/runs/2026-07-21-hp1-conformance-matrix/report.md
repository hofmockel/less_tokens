# HP1 — Live Claude/Codex conformance and savings matrix

**Date:** 2026-07-21
**Backlog item:** HP1 (`BACKLOG.md`)
**Status:** partially complete — infrastructure and 4 of 7 workloads captured for both agents; 3 workloads remain `not_yet_measured`.

## Why this exists

Every public savings claim in `README.md`'s strategy table was either an unlinked percentage
range or a hand-asserted `parity.json` shipped/missing flag. That binary vocabulary conflates
four distinct things: code present, hook configured, event actually fired, and the action
actually enforced/measured — the exact conflation CX28 caught once already (Codex `PostToolUse`
fires but cannot replace tool output). HP1 replaces guessed numbers with a reproducible,
versioned, agent+release-tagged evidence store.

## Methodology

Each of the 7 workloads named in `BACKLOG.md`'s HP1 text
(`agents/common/conformance/workloads.py`) is evaluated per `(workload, agent, release)` cell
against four booleans — `code_present`, `configured`, `event_fired`, `action_enforced` — plus a
`basis` label. A cell is either `"measured"` with a cited fixture, or explicitly
`"not_yet_measured"`; no cell carries a guessed number. Claude releases are dated (no
`claude --version`-equivalent string exists); Codex releases use the existing `X.Y.Z` form from
`.claude/tests/fixtures/codex-hooks/`.

`agents/common/conformance/matrix.json` is the evidence store. `.claude/tools/conformance_matrix.py`
(+ its `.less_tokens/tools/` runpy shim) renders it into `<!-- conformance-matrix: begin/end -->`
blocks in `README.md` and `DOCUMENTATION.md`, mirroring `hook_parity_docs.py`'s render/`--check`
shape. `.claude/tests/unit/test_conformance_matrix.py` pins schema completeness (every workload
has an entry per supported cell), field completeness on measured entries, that every measured
entry's basis is literally `"measured"`, and that the rendered docs match the checked-in evidence.
A CI step (`.github/workflows/tests.yml`, `label-consistency-gate` job) runs
`conformance_matrix.py --check` alongside the existing `hook_parity_docs.py --check`.

## Captured this session

- **`indexed_whole_file_read`** (Claude + Codex) — Claude: `grep-first-read.py` blocked a full
  `Read` of a 389-line/14,546-byte indexed file (threshold 150 lines), redirecting to a targeted
  slice. Codex: `search-first.py` denied an unsearched `cat` of an indexed 855-byte file via the
  native `permissionDecision` contract, then allowed it after a recent search.
  Fixtures: `.claude/tests/fixtures/conformance/indexed_whole_file_read/{claude,codex}/README.md`.
- **`repeated_read_search`** (Claude; Codex `not_yet_measured`) — `context-cache.py` blocked a
  `Read` of a 120-line/3,809-byte file already served within the 300s TTL window. Caveat recorded
  in the fixture: the gate covers `Read`/`Grep`, not raw shell `cat` — a real enforcement-boundary
  gap, stated rather than hidden. Fixture:
  `.claude/tests/fixtures/conformance/repeated_read_search/claude/README.md`.
- **`noisy_command_output`** (Claude + Codex) — Claude: `truncate-output.py` capped a 25,336-char
  Bash output to 5,032 model-visible chars (~80% removed) in-session. Codex: cites CX28's existing
  finding (`DECISIONS.md`) rather than re-capturing — `PostToolUse` fires but `suppressOutput` is
  unsupported, so `code_present: true`, `configured: false`, `action_enforced: false`. Fixture:
  `.claude/tests/fixtures/conformance/noisy_command_output/claude/README.md`.
- **`long_session_compaction`** (Claude + Codex) — Claude: `compact-trigger.py` fired mid-session
  at a 660,189-char transcript, advisory only (no post-compaction size check possible). Codex:
  cites CX20's bounded live probe (19,533→6,588 tokens via the experimental
  `thread/compact/start` app-server method) — advisory only, `action_enforced: false` on both
  sides for different reasons.
- **`bounded_subagent_exploration`** (Claude + Codex) — Claude: a live Explore-type subagent ran
  42 tool uses over ~326s, reporting 77,966 internal tokens; only its final structured report was
  absorbed into the parent. Note: that figure is the harness's subagent-internal token count, not
  a byte count of what the parent absorbed — an apples-to-oranges gap, stated rather than papered
  over. Codex: cites CX30's existing character-count telemetry (prompt/child-final/parent-absorbed
  as separate content-free events; not enforcement, no digest/delegation policy exists). Fixture:
  `.claude/tests/fixtures/conformance/bounded_subagent_exploration/claude/README.md`.

Deliberately **not** used as evidence for any cell: `.claude/state/savings.jsonl`. It's a shared,
non-session-scoped log (generic `session_id`, other processes' entries interleaved) — flagged as
fresh evidence worth capturing for backlog item `PC1`, not usable here.

## Deferred (`not_yet_measured`)

- `edit_verification` (Claude + Codex) — requires an Edit/Write plus read-after-edit/post-edit-diff
  probe; not captured this pass.
- `verbose_final_response` (Claude + Codex) — requires an unmodified-vs-terse Stop-response
  baseline diff; not captured this pass.
- `repeated_read_search:codex` — Codex-side context-cache capture not captured this pass.

`HP1` stays open in `BACKLOG.md` with these three cells named explicitly as outstanding, per the
"delete only when actually done" backlog rule.

## Docs updated

- `README.md` / `DOCUMENTATION.md` — new `#### Conformance matrix` section with the rendered
  `<!-- conformance-matrix -->` block, placed after the existing hook-parity block.
- `README.md`'s strategy table (via `.claude/tools/strategy_registry.py`, never hand-edited
  directly) — the Terse output mode, Tool output truncation, and Compaction trigger rows now link
  to the conformance matrix or state `not yet measured against a versioned workload` instead of
  carrying an unlinked percentage range. The Lean tool output and remaining rows are unchanged —
  they aren't among the 7 versioned workloads and were already honestly hedged.

## Install-health acceptance

`install.py`'s `do_check()` (line ~1879) already fails when a detected Codex executable has
`[features].hooks` disabled (line ~1917) — this satisfies HP1's "install health fails when a
required trusted hook is disabled" acceptance bullet for Codex at the only granularity Codex
exposes non-interactively (per-hook trust has no stable query, documented in the same function).
See `DECISIONS.md` for the citation; no new code was needed.

## Verification run this session

- `python .claude/tools/conformance_matrix.py` — rendered and wrote both docs (no prior content,
  first render).
- `pytest .claude/tests/unit/test_conformance_matrix.py` — 6/6 passed.
- `python .claude/tools/strategy_table_docs.py` — confirmed README already matched the updated
  registry (no drift).
- `python .claude/tools/label_consistency_gate.py` — passed.
- Full gate suite (`hook_parity_docs.py --check`, `changelog_gate.py`, full unit suite) — see
  this run's `CHANGELOG.md`/`BACKLOG.md` entries for final status.
