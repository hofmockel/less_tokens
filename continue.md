# Continue: less_tokens

> **Next focus:** review and commit the `continue` skill migration + freshness-gate work below (nothing is committed yet), then pick the next `BACKLOG.md` item.

## Current state
`main` is at `8a48eba` with a clean history, but the working tree has substantial **uncommitted** changes from this session — 11 modified files, 3 new. Nothing has been committed or pushed. `check_docs.py`, `codex_parity_audit.py`, and the affected unit tests all pass against the working tree as-is.

## What happened this session
- Discovered `continue.md` was 12 commits stale (claimed HEAD `781e2d9`, actual `8a48eba` at the time) — a full `docs-site/` HTML documentation build had shipped after the doc was last written and never got reflected back. Nearly re-scaffolded `docs-site/` from scratch over already-shipped work before a `Write` guard on `build_docs.py` caught it. No lasting damage — the false-start files were deleted before this session ended.
- Root-caused it: the `/continue` skill's own Phase 1 staleness check only runs when a session explicitly invokes `/continue` — a fresh agent that just reads `continue.md` directly (as happened here) never triggers it. `continue` was also a personal *global* skill (`~/.claude/skills/continue/`), not something less_tokens shipped, so it had no per-project enforcement anywhere.
- Fixed both problems:
  - Moved the skill into this repo as the source of truth: `agents/claude/skills/continue/SKILL.md`. The installer's existing generic skill-deploy loop already picks up anything under `agents/claude/skills/`, so it now ships to every project less_tokens is installed into — no `install.py` changes needed.
  - Removed the global copy (`~/.claude/skills/continue/`) per explicit instruction. **Side effect worth knowing:** any repo without less_tokens installed — including `ever_better` itself — no longer has a `/continue` skill available at all. That's an intentional tradeoff (centralize in less_tokens over a global personal skill), not an oversight, but it means `ever_better`'s own session handoffs need a different mechanism now if that repo doesn't install less_tokens.
  - Added an **enforced** freshness gate, not just a documented one: `agents/common/hooks/continue_freshness.py` (regexes the `_Last updated at HEAD \`<hash>\`_` footer, runs `git rev-list --count <hash>..HEAD`), with both a Claude launcher (`.claude/hooks/continue-freshness.py`) and a Codex launcher (`agents/codex/hooks/continue-freshness.py`), wired as `PreToolUse` hooks in `hook_manifest.py`/`parity.json` on both agents. Blocks a raw `Read(continue.md)` with the commit count and a `git log` preview when stale; allows through when current. Verified against the hook script directly, plus `test_continue_freshness.py`/`test_codex_hooks.py`/`test_install_hook_entries.py`/`test_install_codex.py` (58 tests total, all passing).
- Regenerated README/DOCUMENTATION hook-parity tables and the docs-site hook matrix to include `continue-freshness`; fixed the hardcoded hook-count assertion in `test_install_hook_entries.py` (21→22, 11/11 pass).
- Both original BACKLOG rows for this (freshness banner + enforced read-gate) removed as shipped; CHANGELOG `[Unreleased]` entry added.

## Open work
1. **Commit the above** — nothing is committed. `git status --short` shows exactly what changed; the CHANGELOG entry already describes it.
2. See [BACKLOG.md](BACKLOG.md) for what's next after that — top item is widening bash/grep cache keys, still blocked on Codex-side telemetry accumulating.

## Suggested skills
- `$less-tokens` — search and inspect the codebase without dumping large files.
- `$agentsmd` — keep agent-facing docs lean if touching `AGENTS.md` or instruction material.

## Start here
`git status --short` and `git diff` to review this session's changes, then commit. Do **not** re-run `install.py` speculatively first — the hook wiring in `.claude/settings.json` was hand-added to match `hook_manifest.py` and already verified working; a fresh install run should be a no-op but hasn't been checked.

---
_Last updated at HEAD `8a48eba` on 2026-07-16._
