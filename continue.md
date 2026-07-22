# Continue: less_tokens

> **Next focus:** HP1 is fully closed (14/14 matrix cells measured). Pick up **CX31** (wire
> `map_bash_read` into `context-cache.py` — well-scoped, has a clear acceptance test already) or
> the next `BACKLOG.md` "Ready now"/"Next" item.

## Current state

HP1's conformance matrix has all 14 workload:agent:release cells `measured`. This was reached
across two independent sessions that both worked on HP1 in parallel and diverged from the same
base (`97181c8`):

- One session (landed on `origin/main` as `ffae166`, PR #112) refined `repeated_read_search:codex`
  with a more precise 3-probe methodology (a repeated `rg` search over `Bash` IS blocked; a
  repeated whole-file `cat`/`head`/`tail`/`sed -n` read is NOT; the same read IS blocked via the
  opt-in `mcp__filesystem__` shape) and filed **CX31**/**CX32** in `BACKLOG.md`.
- The other session (this one) captured the final 2 workloads, `edit_verification` and
  `verbose_final_response`, for both agents.

The two histories were merged locally (`0ef72f8` merged with `ffae166`) with `matrix.json`,
`BACKLOG.md`, `CHANGELOG.md`, `README.md`, `DOCUMENTATION.md`, and this file hand-reconciled —
taking the more-refined `repeated_read_search:codex` evidence from `ffae166` and keeping the new
`edit_verification`/`verbose_final_response` evidence from `0ef72f8`. All 4 doc/parity gates pass
and the full unit suite passes (1208). Push is in progress; check `git log --oneline -5` and
`git status` to confirm the merge commit landed and `origin/main` is up to date before starting
new work.

## What happened this session

- Captured `edit_verification` for both agents: `post-edit-diff.py` surfaced a real diff (Claude:
  pure `old_string`/`new_string` diffing on an `Edit`; Codex: real `git diff HEAD` on a staged
  `apply_patch` addition), then `read-after-edit.py` genuinely blocked the follow-up re-read on
  both agents. Notable finding: Codex's `read-after-edit.py` *does* call `map_bash_read` (unlike
  `context-cache.py`), so a plain `Bash cat` of a just-edited file was blocked too.
- Captured `verbose_final_response` for both agents: `caveman-reminder.py`/`terse-reminder.py`
  blocked a 654-char/119-word filler-laden response and passed a 78-char/13-word terse rewrite of
  the same underlying content (576 chars / 88% removed) on both agents. Key parity nuance: Codex's
  `terse-reminder.py` reads `payload["response"]` directly, while Claude's `caveman-reminder.py`
  reads the response out of a transcript file via `transcript_path`.
- Method for both: hooks invoked directly with real stdin payloads matching each agent's installed
  schema (no live interactive Claude/Codex session was spawned this run), same precedent as
  `indexed_whole_file_read/codex/README.md`'s method note from 2026-07-21.
- Deleted `BACKLOG.md`'s HP1 row (all acceptance criteria met) and closed out `CHANGELOG.md`'s
  `[Unreleased]` HP1 bullet.
- On push, discovered `origin/main` had moved (PR #112, `ffae166`) with a parallel, more-refined
  `repeated_read_search:codex` capture and CX31/CX32 filings. Merged and reconciled by hand: took
  `ffae166`'s `repeated_read_search:codex` evidence (matrix.json notes + fixture README) as
  authoritative since it's more precise than the version this session had inherited, kept this
  session's `edit_verification`/`verbose_final_response` entries, regenerated `README.md`/
  `DOCUMENTATION.md` via `conformance_matrix.py` (safe — those sections are fully generated), and
  hand-merged the `BACKLOG.md`/`CHANGELOG.md` prose so neither session's findings were lost.

## Open work

Nothing in flight on HP1. Next candidates: **CX31** (the real fix for the `repeated_read_search:codex`
gap — wire `map_bash_read` into `context-cache.py`), **CX32** (research — verify/extend the Codex
hook-contract window past `0.144.6`; local Codex is `0.145.0`), or **D4** (publish reproducible
savings benchmarks, no longer blocked now that HP1 is closed). **HS1**, **IR1**, **CP1** are the
other open P1 research items.

## Suggested skills

- `continue` — when handing off again.
- `less-tokens` — targeted exploration of the hook/budget code before extending captures.

## Start here

Run `git status`/`git log --oneline -5` first to confirm the merge/push landed cleanly. If
continuing straight into new work, pick the next `BACKLOG.md` row per its `Order` column — CX31
is the most concrete pick (real bug, already scoped, acceptance test implied by the capture that
found it).

---
_Last updated after merging `0ef72f8` (this session's HP1 close) with `origin/main` `ffae166`
(parallel HP1 `repeated_read_search:codex` refinement + CX31/CX32) on 2026-07-22._
