# Continue: less_tokens

> **Next focus:** implement CX23's fix — isolate `PostToolUse`-declared entries into their own `hooks.json` matcher group(s), add regression coverage.

## Current state
`main` is clean at `ae0c3b7`, matches `origin/main`. Open PR: [#78](https://github.com/hofmockel/less_tokens/pull/78) (`docs/cx18-close-cx23-file`, doc-only, not yet merged) — closes CX18's research and confirms CX23 at production scale. All CI checks green (Changelog gate included, after the fix below). No source code changed yet.

## What happened this session
- Landed the prior session's pending doc changes (CX18 close + CX23 file) as PR [#78](https://github.com/hofmockel/less_tokens/pull/78).
- Rebuilt CX23's repro at **real production scale** instead of the prior session's 2-entry hand-built test: used `build_codex_hook_entries`/`HOOK_SPECS` to generate the actual 20-entry manifest, swapped every hook script for a transparent stdin-logging shim, wrote it through `codex_hooks_json_value()` into `.codex/hooks.json` exactly as `install.py` would, and ran live `codex exec` turns (`codex-cli 0.142.3`, `-m gpt-5.5 -c model_reasoning_effort=low --dangerously-bypass-hook-trust --dangerously-bypass-approvals-and-sandbox`) against it in a scratch git repo.
- **Confirmed CX23.** Two facts: (1) an isolated single-entry `PostToolUse`-only group never fires at all in headless `codex exec` — generalizes CX17/CX18's non-firing findings to the whole non-`PreToolUse` surface; (2) the same entries sharing the one production matcher-group array with matching `PreToolUse` entries fire anyway, mislabeled `PreToolUse`, with no tool-output field — reproduced for all 11 `PostToolUse`-declared entries in the real manifest (`truncate-output`, `post-edit-diff`, `index-refresh`, `agent-md-budget`, `savings-html`, `compact-trigger`, `lean-output`, `budget-observer`/`context-cache`'s Post wires).
- Promoted CX23 from Research to Ready in `BACKLOG.md` with updated acceptance criteria; added a `CHANGELOG.md [Unreleased]` entry citing the evidence. Both committed to PR #78 alongside the earlier CX18/CX23-filing commit.
- Mid-session, a concurrent session (dual-agent Claude/Codex pattern, same as noted in prior handoffs) merged `main` forward via PR #77 (a continue.md refresh) directly into this PR's remote branch, diverging local history from origin. Reconciled with a clean `git merge origin/<branch>` (no conflicts) before pushing — **lesson repeated from two sessions ago: fetch/check `origin` before pushing to a long-lived branch, this repo has real concurrent-session traffic.**
- Scratch repro harness (`logger.py`, hooks.json builder, scratch git repo) lived in the session scratchpad only — not preserved, not part of this repo. Rebuild it fresh for the fix's regression coverage (see below).
- **PR #78's Changelog gate failed after the CX23 push**: `changelog_gate.py`'s Rule 2 (backlog cross-check) treats any `[ID]`-bracketed citation in `CHANGELOG.md`'s `[Unreleased]` section as "this ID shipped" and fails if that ID still has a heading in `BACKLOG.md`. The CX23 changelog entry used the `**[CX23] ...**` bracket convention while CX23 is intentionally still open (promoted to Ready, not shipped) in `BACKLOG.md` — a real inconsistency, not a false positive. Fixed by rewording the entry's title to drop the bracket citation (`**CX23 confirmed at production scale: ... — fix not yet shipped, still open in BACKLOG.md**`) since nothing shipped yet. Verified locally first (`python3 .claude/tools/changelog_gate.py main` → exit 0) before pushing. **Lesson: only use the `[ID]` bracket convention in a CHANGELOG entry when that ID's BACKLOG.md heading is being removed in the same diff — it signals "shipped," not "documented."**

## Open work
1. **Get PR #78 reviewed/merged** — doc-only, closes CX18 and confirms+promotes CX23. No blockers known.
2. **Implement CX23's fix** (P0, top of `BACKLOG.md`'s Ready now table): redesign `codex_hooks_json_value()` (`agents/common/hooks/hook_manifest.py:281-292`) to isolate `PostToolUse`-declared entries into their own matcher-group array(s), separate from `PreToolUse` entries — do not just interleave differently; the isolation itself is what stops the misfire (confirmed: an isolated `PostToolUse`-only group silently doesn't fire, which is strictly better than today's mislabeled/wrong-payload firing).
3. Add regression coverage for the fix — fixture-based is fine (doesn't need a live `codex exec` call): assert the grouping structure itself keeps every `PostToolUse` entry out of any group containing a `PreToolUse` entry with an overlapping matcher. `.claude/tests/unit/test_codex_event_contract.py` or a new test file near `hook_manifest.py`'s existing tests is the natural home — check `install.py`'s and `hook_manifest.py`'s current test coverage first.
4. Record the still-open caveat in `parity.json`/`DOCUMENTATION.md`: Codex `PostToolUse` hooks are **unconfirmed/non-functional in headless `codex exec`** regardless of grouping — the isolation fix stops the misfire but does not restore real post-tool behavior. That needs an interactive `codex` TUI test, same untested gap CX17/CX18 left open (not scriptable for unattended live testing — reopen together once feasible).
5. **CN1** (P2, still just filed) — resolve open design questions (hard-block vs warn push; what "update" means in a bare git hook), then implement the pre-push freshness gate.
6. Third `parity.json` status value question (from several sessions ago) — still open, low priority, revisit only if it resurfaces naturally.

## Notes for next session
- `codex` CLI installed locally (`codex-cli 0.142.3`, `which codex` → `/opt/homebrew/bin/codex`). Use `-m gpt-5.5` explicitly. `-c model_reasoning_effort=low` keeps turns fast. macOS has no `timeout`/`gtimeout` by default — run `codex exec` in the background and poll/monitor rather than trying to wrap it in `timeout`.
- `codex_hooks_json_value()`'s return value is the **value of a `"hooks"` key**, not a standalone file — the full file needs `{"hooks": <value>}`. A first repro attempt this session wrote the bare array as the whole file and got a parse error (`invalid type: map, expected a sequence`) that had nothing to do with CX23 — pure harness bug, easy to repeat if rebuilding the harness from scratch without rereading `install.py:1038`.
- This repo has real concurrent-session (dual-agent) traffic on shared branches — fetch before pushing to any branch that isn't brand new, even mid-session.

## Suggested skills
- `$bugfix` may now fit CX23 — the research spike is done, root cause and fix shape are both known; it's a scoped, single-cause fix (regroup + test) rather than open-ended investigation.

## Start here
Check whether PR #78 merged (`gh pr view 78`). Then read `BACKLOG.md`'s CX23 row (now in the Ready now table) for full evidence and acceptance criteria, and start the fix at `agents/common/hooks/hook_manifest.py:281` (`codex_hooks_json_value`).

---
_Last updated at HEAD `ae0c3b7` (PR #78 open on top, CI green, not yet merged) on 2026-07-18._
