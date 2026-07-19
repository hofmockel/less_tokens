# Continue: less_tokens

> **Next focus:** CX19 (P1, Ready) — implement per approved plan at
> `/Users/michael/.claude/plans/floating-spinning-waffle.md`. Research done. No code written yet.

## Current state
CX25 shipped — merged via PR #83 (`d02f918`), not the direct-to-`main` push the prior handoff
flagged as a possible deviation: `main` is branch-protected (confirmed this session — a direct
`git push origin main` was rejected, "Changes must be made through a pull request"), so PR #83 is
actually consistent with this repo's established CX19–CX24 branch+PR pattern. `main` is at `e57815a`, working tree clean. The prior refresh merged as PR #84 with a stale
self-referential HEAD anchor (`18bffd2`, written before that PR's own base commit was known) —
this commit fixes the anchor and this paragraph's accuracy in a follow-up PR rather than amending
a merged commit.
**Branch `fix/cx19-semantic-read-fixtures` is stale** — it still points at the old local-only
`18bffd2` (content-identical to `d02f918`/PR #83 but a different SHA, predates the
branch-protection discovery) and is not based on current `main`. Rebase it onto `main` before
starting CX19 work. No CX19 implementation exists yet.

## What happened this session
- Confirmed CX25 landed via PR #83, and confirmed why: `main` push protection.
- Researched CX19 in full: read every hook wrapper (`agents/codex/hooks/{search-first,read-guard,
  auto-slice,grep-first-read,read-after-edit,continue-freshness}.py`) and shared logic
  (`agents/common/hooks/{search_first,read_guard,auto_slice,grep_first_read,read_after_edit,
  continue_freshness}.py`) — exact block/allow exit codes, message prefixes, state-file formats
  (`last-search`, `last-search.json`, `last-edit.json` under `LESS_TOKENS_STATE_DIR`), and config
  wiring (thresholds, window seconds) per hook.
- Key finding: today's `_payloads_for_token` in `test_codex_event_contract.py` never seeds hook
  state, so 5 of 6 gate hooks only ever exercise their **allow** path — block path is untested.
  `continue-freshness` isn't exercised at all (no `continue.md`-named fixture exists today).
- Wrote and got user approval on a 7-step implementation plan (add scenario dimension to fixtures,
  outcome table, rewritten assertions, error-agnosticism coverage, unknown-MCP-tool fail-open test,
  Stop-wiring regression guard, BACKLOG/CHANGELOG/continue.md updates). Full plan file has exact
  block-message prefixes and state-file shapes needed — read it before re-deriving any of this.

## Open work
CX19 implementation itself — not started. See plan file above for the 7 steps; all research
needed to execute them is already captured there. After CX19: next backlog item per `BACKLOG.md`
order.

## Suggested skills
- None specific — continue straight from the approved plan, no bugfix/bug-hunt shape needed.

## Start here
Read `/Users/michael/.claude/plans/floating-spinning-waffle.md` in full, then start on step 1
(add scenario dimension to `_payloads_for_token` in `.claude/tests/unit/test_codex_event_contract.py`).

---
_Last updated at HEAD `e57815a` on 2026-07-18._
