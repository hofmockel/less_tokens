# Continue: less_tokens

> **Next focus:** push branch `win1-platform-audit` and open a PR against `main`.

## Current state

PR #128 (PT1-9) merged into `main` (`3b416bf`). `BACKLOG.md` on `main` is now empty — both
**Ready now** and **Next** tables have zero rows. Branch `win1-platform-audit` (off latest
`origin/main`, local HEAD `9cd725f`, not yet pushed) resolves **WIN1** (the Windows-CI-breakage
research spike PT9 itself proposed) in the same session it was proposed, so it was never actually
landed as a `BACKLOG.md` row anywhere reachable from `main`. `dev.py unit`: 1195 passed.
`changelog_gate.py`, `win_platform_audit.py`: clean. Working tree otherwise clean.

## What happened this session

- Investigated whether one mechanical guard could catch the ~8 independent Windows-only CI bugs
  in `CHANGELOG.md`. Verdict (`DECISIONS.md` WIN1): only two are the same recurring root cause —
  bare extensionless launcher paths `.exists()`-checked with no platform-suffix branch (PT9's
  `WinError 193`, and an earlier `python`-vs-`python.exe` installer bug), and POSIX-only
  `subprocess` kwargs (`start_new_session=True`) used with no `sys.platform`/`os.name` branch. The
  other six (console `cp1252` encoding, `Path.relative_to` backslash separators, `SYSTEMROOT`
  env-stripping) are each a structurally different one-off shape — left as already-fixed point
  patches, not folded into a generic detector.
- Shipped `.claude/tools/win_platform_audit.py`, an AST walk flagging either pattern unless the
  enclosing function compares against the literal `"win32"`/`"nt"`. Wired into
  `.pre-commit-config.yaml` and the `label-consistency-gate` CI job (`.github/workflows/tests.yml`).
- New tests `.claude/tests/unit/test_win_platform_audit.py` (7 cases) reconstruct the literal
  pre-fix `lean-output.py`/`listing-guard.py` `_python()` code and the pre-`_detach_kwargs`
  `index-refresh.py` code and assert both are flagged; assert the real fixes and `install.py`'s
  `launcher_rel()` (never calls `.exists()`, so isn't the bug shape) are not false-positived.
- `CHANGELOG.md`/`DECISIONS.md` updated; no `BACKLOG.md` edit needed (WIN1 was never landed there).

## Open work

None in `BACKLOG.md` — it's empty on `main`. Push and PR this branch; after that, the backlog
needs new items proposed before there's a next thing to pick up.

## Suggested skills

- `/less-tokens` — codebase search before reading files directly.
- `/bugfix` — once new `BACKLOG.md` rows exist.

## Start here

`git push -u origin win1-platform-audit`, then `gh pr create --base main --head win1-platform-audit`.

---
_Last updated at HEAD `9cd725f` on 2026-07-26._
