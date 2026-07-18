# Continue: less_tokens

> **Next focus:** get PR #79 merged (CX23 fix), then move to CX19 (top of `BACKLOG.md`'s Ready now table).

## Current state
`main` is at `c5a8afe` (PR #78 merged this session — closed CX18, confirmed+promoted CX23). CX23's fix is implemented on branch `fix/cx23-isolate-post-tool-use-groups` (HEAD `98aa56e`), pushed, PR [#79](https://github.com/hofmockel/less_tokens/pull/79) open — CI was still running when this session ended; check `gh pr checks 79` before doing anything else. Working tree is clean.

## What happened this session
- Merged PR #78 (doc-only, all 26 checks green) after user confirmation.
- Implemented CX23's fix: `codex_hooks_json_value()` (`agents/common/hooks/hook_manifest.py:281`) now buckets flat hook entries by declared `event` before nesting, so `PreToolUse` and `PostToolUse` entries land in separate matcher-group arrays instead of one shared array. This stops the confirmed misfire (every `PostToolUse`-declared entry firing mislabeled `PreToolUse`) — it does **not** restore real `PostToolUse` dispatch; an isolated `PostToolUse`-only group still never fires in headless `codex exec` (CX23's fact 1, still true). `flatten_codex_hooks()` already flattened across groups unconditionally, so `install.py`'s wire/unwire callers needed no changes.
- Added regression tests in `.claude/tests/unit/test_hook_manifest_parity.py`: group isolation (no group mixes declared events), round-trip through `flatten_codex_hooks`, empty-input case.
- Recorded the still-open caveat in `DOCUMENTATION.md`'s Known limitations: Codex `PostToolUse` hooks remain unconfirmed/non-functional in headless `codex exec` regardless of grouping, pending an interactive-`codex`-TUI retest. Left `parity.json`'s schema binary (`shipped`/`missing`) per the CX17 precedent — no new field added there, the caveat lives in prose only.
- Removed CX23's row and detail block from `BACKLOG.md`, renumbered the Ready-now/Next tables; added a `[CX23]` `CHANGELOG.md [Unreleased]` entry (the historical "confirmed at production scale" entry from PR #78 stays as-is — new entry documents the fix itself, not a rewrite).
- Verified: `dev.py unit` (943 passed), full `.claude/tests` (1033 passed), `changelog_gate.py main` (exit 0) — all before pushing.
- This session's own transcript hit the `compact-trigger` threshold mid-handoff (632k chars) — a live example of the hook this repo ships, firing on the *session's* transcript rather than anything less_tokens-specific. Not a repo bug; user was told to `/compact` or start fresh.

## Open work
See [BACKLOG.md](BACKLOG.md) — CX23 is gone from Ready now; **CX19** (replace synthetic Codex hook smoke tests with semantic fixtures) is now top of the Ready-now table. CN1 (P2, pre-push freshness gate design questions) and the third `parity.json` status-value question remain open at low priority, unchanged from prior sessions.

## Suggested skills
- None specific — CX19 is a fresh implementation task once PR #79 is in, not a bugfix/bug-hunt fit.

## Start here
Run `gh pr checks 79`. If green, `gh pr merge 79 --squash --delete-branch`, pull `main`, then start CX19 per its `BACKLOG.md` row.

---
_Last updated at HEAD `98aa56e` (PR #79 open on `fix/cx23-isolate-post-tool-use-groups`, CI status unconfirmed at write time) on 2026-07-18._
