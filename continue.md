# Continue: less_tokens

> **Next focus:** land CX21 (fix `.codex/hooks.json` schema so installed Codex hooks actually load).

## Current state
`main` has moved 19 commits since the last handoff (SA1, CX16, F1, B1/B2 Codex-truncation fixes, backlog reorg, and more — see `git log --oneline 936f0ed..HEAD`). This session's own branch, `cx17-codex-hooks-schema-finding`, is clean and pushed; PR [#70](https://github.com/hofmockel/less_tokens/pull/70) is open against `main`, docs-only (`BACKLOG.md`/`CHANGELOG.md`/`DECISIONS.md`), no functional code touched.

## What happened this session
- Worked CX17 (backlog Research item: does Codex's `PostToolUse` hook stdout actually replace what the model sees?). Live-tested with real `codex exec` calls (codex-cli 0.142.3), planting a random sentinel inside `truncate_bash()`'s head/tail omission window.
- Found this repo's own installed `.codex/hooks.json` fails to parse under the currently-installed CLI — the installer emits a flat `{"hooks":[{event,matcher,command}]}` shape, but the CLI actually wants `{"hooks":[[{event,matcher,hooks:[{type,command}]}]]}` (one extra list level, Claude-style nested hook groups). This silently no-ops **all 20** of this repo's dogfooded Codex hooks on this machine — no visible error outside `--json` trace inspection.
- Even after hand-correcting the schema and forcing `--dangerously-bypass-hook-trust`, `PostToolUse` still never fired at all in `codex exec` (confirmed via a wildcard debug tap: 0 `PostToolUse` payloads captured vs. 1 clean `PreToolUse` payload in the same run). So CX17's original replacement-contract question was never actually reachable — the sentinel came back fully intact either way.
- `.codex/hooks.json` was restored to its original (broken) state afterward — no live fix applied, since the real fix belongs in the installer's `wire_codex_hooks_json` (`install.py:967`), not a hand-edited file.
- Filed **CX21** (P0) for the schema bug, now BACKLOG.md's top "Ready now" row. Removed CX17's row (research outcome, recorded in `DECISIONS.md` instead per the Research-item convention). `parity.json`'s `truncate-output.codex: "shipped"` is now known-inaccurate but wasn't changed — its vocabulary is binary (`shipped`/`missing`) and neither value fits "wired but broken"; flagged as a follow-up, not fixed.
- Also picked up an unrelated stale WIP stash from `sa2-subagent-fanout` while switching branches — resolved a merge conflict in `BACKLOG.md`/`CHANGELOG.md` (main still has SA2's own row/entry unshipped) and folded both into this commit correctly.

## Open work
1. **CX21** — fix `wire_codex_hooks_json` to emit the correct nested schema; add a smoke test that actually invokes `codex exec` (or an equivalent fixture-based parse check) so schema drift fails loudly next time. See `BACKLOG.md` for full acceptance criteria.
2. Reopen **CX17** properly once CX21 lands — still need to isolate whether the `PostToolUse` non-firing was exec-mode-specific or purely the schema bug (interactive `codex` TUI wasn't tested; not scriptable for an unattended run).
3. Decide a third `parity.json` status value (or equivalent) for "wired but unverified/broken" — `truncate-output.codex` shouldn't read `"shipped"` today.
4. PR #70 itself just needs review/merge — it's small and self-contained.

## Suggested skills
- `$less-tokens` — inspect `install.py`'s `wire_codex_hooks_json` and the hook manifest before touching CX21.
- `$bugfix` — CX21 is a well-scoped, single-cause fix once picked up.

## Start here
Read `BACKLOG.md`'s CX21 row, then open `install.py:967` (`wire_codex_hooks_json`) and fix the emitted schema to match the nested `Vec<Vec<MatcherGroup>>` shape documented there.

---
_Last updated at HEAD `a6e8c9b` on 2026-07-17._
