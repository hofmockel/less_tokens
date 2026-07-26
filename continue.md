# Continue: less_tokens

> **Next focus:** confirm PR #128's CI is actually green now (PT9 just fixed it), merge, then
> **CX32** is the only remaining Next-table item.

## Current state

Branch `land/pt1-pt8-eb-strategy-review` pushed, PR
[hofmockel/less_tokens#128](https://github.com/hofmockel/less_tokens/pull/128) open against
`main`. Working tree clean. Contains the eb-strategy-review cluster (PT1-PT8) plus **PT9**, which
fixes the CI that PT1-PT8 left red. `dev.py unit`: 1184 passed. `BACKLOG.md`'s Ready-now table is
empty.

**PT9 — the CI itself was broken, independent of PT1-PT8's fixes.** `.codex/` is entirely
gitignored (`install.py` writes machine-specific absolute paths into `.codex/hooks.json`), and CI
never had a step that generated it — so `codex_parity_audit.py` (`label-consistency-gate`) and
`test_bugPT8_subagent_metrics_guidance_wired.py` (`Test` matrix) failed on every OS/Python
combination regardless of how many PT items landed, because PT1-PT8 only ever edited the
author's pre-existing local `.codex/` copy by hand — invisible to git, so a fresh clone never had
it. Fixed by adding a "Refresh this repo's own dogfooded Codex hook install"
(`install.py --self-refresh --agent codex --skip-deps --create-venv --no-build`) step to both the
`test` and `label-consistency-gate` jobs in `.github/workflows/tests.yml`. Running a *real*
self-refresh (rather than trusting the hand-edited copy) surfaced two more masked bugs, both
fixed in the same commit: (1) `install.py`'s `agents/codex/hooks` copy spec blanket-copied the
orphaned `truncate-output.py` back in every time — excluded it from the copy spec like `PT4`
excluded `parity.json`; (2) `codex_parity_audit.py` would have stayed red forever regardless,
since `compact-trigger`/`terse-output`/`savings-html` can never wire `Stop` in headless
`codex exec` (`CX18`, accepted/permanent) — added an `ACCEPTED_UNWIRED` carve-out so only a real
regression (missing script, broken `hooks.json`) still fails for those three. Also deleted the
`PT4` row `BACKLOG.md` had left behind (already shipped in `CHANGELOG.md`), which is what failed
the `Changelog gate` job. Verified against a from-scratch working-tree copy (no `.git`, no
`.codex`, no `.less_tokens`) with Codex-binary detection bypassed to mirror a GitHub-hosted
runner with no Codex installed — `dev.py unit` 1184 passed, `codex_parity_audit.py` clean,
`changelog_gate.py` clean.

**Second push (`f7fb851`): a fourth bug, Windows-only.** After the first PT9 push, `Changelog
gate` and `Label consistency gate` went green immediately, and every ubuntu/macos `Test` leg
passed — but all three `windows-latest` `Test` legs failed with
`OSError: [WinError 193] %1 is not a valid Win32 application`. Cause: `listing-guard.py`,
`lean-output.py`, and `index-refresh.py` each resolved their subprocess launcher as the bare,
extensionless `.less_tokens/bin/python` with no platform check; `write_python_launcher()` always
writes that POSIX shell script *and* a `.less_tokens/bin/python.cmd` Windows sibling, so once the
new self-refresh step created a real `.less_tokens/` on Windows too, the bare (non-executable)
path existed and got handed straight to `subprocess.run`. Fixed with a shared
`venv_python(repo)` helper in `_codex_runtime.py` (checks `sys.platform` and appends `.cmd` on
`win32` before checking existence) used by all three hooks. `dev.py unit`: 1188 passed. Verified
the platform branch with a `sys.platform="win32"` monkeypatch (no Windows machine available
locally) — real confirmation is PR #128's own Windows CI legs on this second push.

GitHub's CodeQL autofix bot pushed two unrelated small fixes directly to this branch
(`0df276f`/`14772c3`, empty-except and implicit-string-concat lints) after PR #128 opened; rebased
cleanly on top, no conflicts.

## What happened this session

- User asked to fix PR #128's CI failures directly (not another `/bugfix` backlog item).
- Pulled every failed job's log (`gh run view --log-failed`) rather than guessing from the
  status-check summary; found three independent gates red: `Test` matrix (all OS/Python),
  `Label consistency gate` (`codex_parity_audit.py`), `Changelog gate`.
- Root-caused all three (see PT9 above) rather than patching symptoms — the local `.codex/` on
  this machine already had everything PT1-PT8 claimed, which is exactly why the gap (CI never
  generates `.codex/` at all) went unnoticed across eight prior sessions.
- Verified the fix by simulating a fresh CI checkout locally (`rsync`-copied the working tree
  minus `.git`/`.codex`/`.less_tokens`, patched `detect_codex_releases()` to return `[]` so the
  local ChatGPT.app-bundled Codex binary — which is not present on GitHub-hosted runners — doesn't
  block `--self-refresh`) before committing, rather than pushing and hoping.
- Committed as `PT9` and pushed to `land/pt1-pt8-eb-strategy-review`.

## Open work

See [BACKLOG.md](BACKLOG.md) — Ready now table is empty. Next table: **CX32** (research — verify
Codex hook contract past 0.144.6) is the only remaining item.

## Suggested skills

- `/less-tokens` — codebase search before reading files directly.

## Start here

Check PR #128's CI on the latest commit (`f7fb851`) — should be green now, including the
`windows-latest` `Test` legs. If it is, merge, then start CX32 (research spike, no `/bugfix`
needed). If some job is still red, re-pull its log with `gh run view --log-failed` before
assuming PT9 didn't work — four independent root causes were found and fixed across two pushes
here, not one bug; check whether it's a fifth one or a flake.

---
_Last updated at HEAD `f7fb851` on 2026-07-26._
