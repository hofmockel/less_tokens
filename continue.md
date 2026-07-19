# Continue: less_tokens

> **Next focus:** CX19 (P1, Ready) — implement per approved plan at
> `/Users/michael/.claude/plans/floating-spinning-waffle.md`. No code written yet.

## Current state
`main` clean at `1f59a6b`. Since the last handoff, 5 unrelated docs commits landed (`sources.md`
triage work, #85-#88) — no CX19 code exists anywhere. Branch `fix/cx19-semantic-read-fixtures`
still only touches `BACKLOG.md`/`continue.md`/`sources.md` docs (confirmed again this session via
`git diff main..fix/cx19-semantic-read-fixtures --stat`), no test/fixture code — rebase it onto
`main` before use, or just branch fresh from `main`.

## What happened this session
- Re-verified the approved plan is still accurate: read it in full, cross-checked its "no CX19 code
  exists yet" and "branch is docs-only" claims against current `main` — both hold.
- A separate Explore-agent pass this session independently re-researched the same hook set and
  proposed a much larger redesign (per-script fixture tables, new production telemetry for unknown
  tool names, etc.) — **do not use that; it's superseded.** The approved plan below is smaller,
  test-only (no `agents/` source changes), and already has user sign-off. Follow it, not the
  Explore report.
- No code written. Session paused here on user request to write this handoff.

## Open work
CX19 implementation — 7 steps, all in `/Users/michael/.claude/plans/floating-spinning-waffle.md`:
1. Add a scenario dimension (`no-state` vs `state-seeded`) to `_payloads_for_token` in
   `.claude/tests/unit/test_codex_event_contract.py`.
2. Add a `(script_name, token, scenario_name) → (expected_code, expected_substring)` outcome table.
3. Rewrite `test_codex_hook_entry_accepts_representative_payload` to assert against that table
   (keep the existing traceback/JSONDecodeError floor checks).
4. Add error-agnosticism scenarios (error-shaped `tool_response`, same expected outcome).
5. Add `test_codex_unknown_mcp_tool_fails_open` (all 6 gate hooks, not just `search-first`).
6. Add `test_codex_has_no_stop_wiring_yet` regression guard.
7. Update `BACKLOG.md` (delete CX19 row), `CHANGELOG.md` (`[CX19]` entry), `continue.md`.

Exact block-message prefixes and state-file shapes needed for step 1 are already in the plan file —
don't re-derive them. After CX19 ships: next item is `BACKLOG.md`'s **Ready now** order (currently
empty after CX19; next pull from **Next**, top of table).

## Suggested skills
- None specific — continue straight from the approved plan.

## Start here
Read `/Users/michael/.claude/plans/floating-spinning-waffle.md` in full, then start on step 1.

---
_Last updated at HEAD `1f59a6b` on 2026-07-18._
