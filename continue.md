# Continue: less_tokens

> **Next focus:** capture the 3 remaining `not_yet_measured` HP1 cells, or move to the next
> `BACKLOG.md` item — HP1's infrastructure and doc/CI wiring are done.

## Current state

HP1's plan (`/Users/michael/.claude/plans/validated-scribbling-wirth.md`, steps 1-10) is fully
built except for evidence coverage. `agents/common/conformance/matrix.json` has 11 of 14
workload:agent:release cells with real live-captured evidence; 3 are honestly `not_yet_measured`
(`repeated_read_search:codex`, `edit_verification:{claude,codex}`, `verbose_final_response`
already had both agents `not_yet_measured` — unchanged). `.claude/tools/conformance_matrix.py`
(+ `.less_tokens/tools/` runpy shim) renders the matrix into `#### Conformance matrix` sections in
`README.md`/`DOCUMENTATION.md`. `README.md`'s strategy table (via `strategy_registry.py`) links
its terse-output/truncate-output/compact-trigger rows to the matrix instead of carrying unlinked
percentages. `.claude/tests/unit/test_conformance_matrix.py` (6 cases) and a
`conformance_matrix.py --check` CI step in `tests.yml` are both in place. `DECISIONS.md` cites
`install.py:do_check()` for HP1's install-health bullet. `BACKLOG.md`'s HP1 row and the
`[Unreleased]` `CHANGELOG.md` entry both name the 3 outstanding cells explicitly. Full writeup:
`reports/runs/2026-07-21-hp1-conformance-matrix/report.md`.

Working tree was committed and pushed to `main` this session — should be clean at HEAD after
this handoff (verify with `git status` before starting new work).

## What happened this session

- Regenerated docs via the tools rather than hand-editing generated blocks — caught myself
  starting to hand-edit `README.md`'s strategy table directly and reverted, since `continue.md`
  itself (this file, previous version) warned that table is `strategy_registry.py`-generated.
  Lesson for next time: always check for a `_docs.py`/`_registry.py` generator before editing
  anything between `<!-- ... -->` markers.
- All 4 doc/parity gates pass (`conformance_matrix.py --check` on both the real tool and the
  Codex shim, `hook_parity_docs.py --check`, `strategy_table_docs.py --check`,
  `label_consistency_gate.py`, `changelog_gate.py`), plus the full unit suite (1115 passed).
- Did not re-run the Codex-side `repeated_read_search` capture, or either agent's
  `edit_verification`/`verbose_final_response` — those need a fresh bounded live-capture session
  each, same protocol as the ones already done (see fixture READMEs under
  `.claude/tests/fixtures/conformance/*/claude/` for the pattern to mirror).

## Open work

Only the 3 `not_yet_measured` cells remain for HP1 to close for real:
1. `repeated_read_search:codex:0.144.6` — mirror the Claude `context-cache.py` capture
   (`.claude/tests/fixtures/conformance/repeated_read_search/claude/README.md`) against the Codex
   adapter, same bounded live-capture style used for `indexed_whole_file_read:codex`.
2. `edit_verification` (both agents) — needs a real Edit/Write plus read-after-edit/post-edit-diff
   probe; not yet attempted this session.
3. `verbose_final_response` (both agents) — needs an unmodified-vs-terse Stop-response baseline
   diff; not yet attempted.

Once all 14 cells are `measured`, delete HP1's `BACKLOG.md` row per the "delete only when actually
done" rule and add a closing `CHANGELOG.md` entry. Until then, keep tightening the row rather than
deleting it.

## Suggested skills

- `continue` — when handing off again.
- `less-tokens` — targeted exploration of the hook/budget code before extending the remaining
  workload captures.

## Start here

Pick one of the 3 outstanding cells above (Codex `repeated_read_search` is the most similar to
work already done this session, so probably the fastest next capture), follow the same
bounded-live-capture-plus-fixture-README pattern as the existing entries in
`agents/common/conformance/matrix.json`, then re-run `conformance_matrix.py` to regenerate docs.

---
_Last updated at HEAD `1c34ffb` on 2026-07-21 (pre-commit — see git log for the actual HP1-wiring
commit hash once pushed)._
