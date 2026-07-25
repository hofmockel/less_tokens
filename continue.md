# Continue: less_tokens

> **Next focus:** push `feat/cn1-pre-push-continue-freshness` and open a PR for CN1 (now
> committed). After that, CX32 is the only remaining Next-table item.

## Current state

On branch `feat/cn1-pre-push-continue-freshness`, 1 commit ahead of `origin/main` (`a92d63b` —
[#123](https://github.com/hofmockel/less_tokens/pull/123) merged as a squash commit, superseding
the `410eff2` this handoff previously pointed at). Working tree clean, **unpushed, no PR open**.
That one commit is CN1:

- `agents/common/hooks/continue_freshness.py` — added `check_continue_freshness_at_ref` (checks
  continue.md as committed at an arbitrary ref, not the worktree+HEAD) and fixed a real bug:
  `_staleness_result` now exempts the exact 1-commit gap that's structurally unavoidable right
  after any commit that updates continue.md (it can't embed its own not-yet-existing hash) —
  the same gap `410eff2` "closed" only by adding a sentence, not fixing the checker.
- `agents/common/hooks/pre-push-continue-freshness.py` (new) — the native `pre-push` entry point.
- `install.py` — `wire_pre_push_hook`/`unwire_pre_push_hook`/`_pre_push_script_rel`, wired into
  the main install/uninstall flow. First native `.git/hooks` install surface in this toolkit
  (distinct from the JSON-based Claude/Codex tool-hook wiring); composes with, never clobbers, a
  pre-existing host-owned `pre-push` hook.
- `.claude/tests/unit/test_install_prepush.py` (new, 10 cases) + 4 new cases in
  `test_continue_freshness.py`.
- `BACKLOG.md` — deleted the CN1 row. `CHANGELOG.md` — added the `[CN1]` `[Unreleased]` entry.

Full suite: `.claude/bin/python -m pytest .claude/tests` — **1262 passed**. Verified end-to-end
against a throwaway `git clone --local` target (both dry-run and a real install), including
simulating stale/fresh/branch-deletion `pre-push` stdin payloads by hand.

## What happened this session

- Closed the branch/PR deferral flagged twice in prior handoffs: rebased `docs/d2-hook-config-example`
  onto `origin/main` (dropped a now-duplicate D2 commit — main already had it via a separately
  merged PR #122 with an identical diff), then pushed and opened
  [hofmockel/less_tokens#123](https://github.com/hofmockel/less_tokens/pull/123). The branch's
  remote copy had already been auto-deleted after #122 merged, so this was a fresh push, not a
  force-push over anyone else's work.
- Implemented **CN1** per the design above (resolved both of its open design questions: hard-block
  not warn-only; staleness-gating only, not auto-regeneration — a bare git hook can't call an LLM).

## Open work

See [BACKLOG.md](BACKLOG.md) — **Next** table: only **CX32** remains (Research: verify Codex hook
contract past 0.144.6). Separately: `feat/cn1-pre-push-continue-freshness` needs pushing and a PR.

## Suggested skills

- `/bugfix` — not applicable to CX32 (it's a research spike, not a backlog-row edit).
- `/less-tokens` — for codebase search in this repo before reading files directly.

## Start here

Push `feat/cn1-pre-push-continue-freshness` and open a PR (same shape as #123), then move to CX32.

---
_Last updated at HEAD `a92d63b` on 2026-07-24._
