# Continue: less_tokens

> **Next focus:** investigate CX24 (`mcp__filesystem__.*` Codex matcher may be dead in a default install) before resuming CX19's live-capture fixture work.

## Current state
`main` is clean at `ed4b2c7` (CX23's fix, PR #79) plus its continue.md refresh (PR #80) — both merged this session. Working branch `docs/file-cx24-filesystem-matcher` (HEAD `5a9e997`) has PR [#81](https://github.com/hofmockel/less_tokens/pull/81) open, doc-only, mergeable — files CX24 and reorders `BACKLOG.md` so it blocks CX19. Check `gh pr checks 81` before anything else.

## What happened this session
- Merged PR #79 (CX23's fix) and PR #80 (continue.md refresh) — both already implemented/queued from the prior session.
- Started CX19 (replace synthetic Codex hook contract-test payloads with real ones). User chose "multi-version fixture store from the start" over single-version.
- Before building anything, ran live `codex exec` probes (`codex-cli 0.142.3`, scratch repo, isolated PreToolUse/PostToolUse hook groups) to validate assumptions CX19 would otherwise bake into fixtures:
  1. **Reconfirmed `PostToolUse` never fires in headless `codex exec`**, even after CX23's isolated-group fix — an isolated `PostToolUse:.*` group alongside an isolated `PreToolUse:.*` group only fired Pre. Genuine post-execution payloads (real `tool_response`) stay uncapturable live pending interactive-TUI testing (same open gap as CX17/18/23).
  2. **Found `mcp__filesystem__.*` — the matcher gating 7 Codex hooks — may never fire at all.** Asked Codex to read a file "with your file reading tool, not a shell command": under `--ignore-user-config` (clean, no personal plugins) it reported no dedicated read tool exists and only shell (`Bash`) can touch local files; with personal plugins loaded it used `mcp__node_repl__js` instead. Neither run produced `mcp__filesystem__*`. `install.py:1796`'s own smoke-check payload for this matcher was never live-verified either — same class of unverified assumption CX17/18/23 kept finding elsewhere in the Codex adapter.
- Filed this as **CX24** (P0, Research) in `BACKLOG.md` with full evidence, reordered it ahead of CX19 (CX19's "real-shape fixtures" are pointless for a matcher that may not be real), and paused CX19 mid-investigation (no fixture/code changes made yet — task was research-only this session).
- Scratch probe harness lived in the session scratchpad only (`cx19-probe/`, not preserved) — rebuild if a future session needs to re-run live probes.

## Open work
See [BACKLOG.md](BACKLOG.md). Ready-now order is now: **CX24** (new, P0) → **CX19** (blocked on CX24) → CN1. CX24's acceptance: confirm live whether *any* Codex configuration ever emits `mcp__filesystem__*`; if not, redesign the 7 affected hooks (`search-first`, `read-guard`, `auto-slice`, `grep-first-read`, `read-after-edit`, `continue-freshness`, plus shared wires in `budget-observer`/`context-cache`/`truncate-output`) to key off `Bash`-based reads instead, or downgrade their Codex claims in `parity.json`/`DOCUMENTATION.md`.

## Suggested skills
- None specific — CX24 is a live-testing investigation (same shape as CX17/18/23's spikes), not a bugfix/bug-hunt fit until root cause is confirmed.

## Start here
Run `gh pr checks 81`; merge if green. Then investigate CX24: try a few more Codex read-triggering prompts (and check whether an explicit user-configured MCP filesystem server ever produces the `mcp__filesystem__` prefix) to settle whether the matcher is dead across the board or only in untested configurations, then act per its acceptance criteria.

---
_Last updated at HEAD `5a9e997` (PR #81 open on `docs/file-cx24-filesystem-matcher`, CI status unconfirmed at write time) on 2026-07-18._
