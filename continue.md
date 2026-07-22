# Continue: less_tokens

> **Next focus:** capture the 2 remaining `not_yet_measured` HP1 cells (`edit_verification`,
> `verbose_final_response`, both agents), or move to the next `BACKLOG.md` item.

## Current state

HP1's matrix now has 12 of 14 workload:agent:release cells with real live-captured evidence; only
`edit_verification:{claude,codex}` and `verbose_final_response:{claude,codex}` remain
`not_yet_measured`. All 4 doc/parity gates pass (`conformance_matrix.py --check` on both the real
tool and the Codex shim, `hook_parity_docs.py --check`, `strategy_table_docs.py --check`,
`label_consistency_gate.py`) plus the full unit suite (1115 passed). Working tree is clean at HEAD
`7bd4829`.

## What happened this session

- Captured `repeated_read_search:codex:0.144.6` (`.claude/tests/fixtures/conformance/repeated_read_search/codex/`).
  Method: `context-cache.py` only records a read on `PostToolUse`, never `PreToolUse` — so the
  correct probe sequence is Pre (allow) → Post (record) → Pre (now blocked), not two bare
  PreToolUse calls (the first attempt with two PreToolUse-only calls silently no-opped — worth
  remembering if this pattern comes up again for `edit_verification`).
- Found a real, more severe gap than the Claude-side one: `context-cache.py` never applies
  `map_bash_read` (unlike `search-first.py`/`read-guard.py`/`grep-first-read.py`/`auto-slice.py`/
  `read-after-edit.py`/`continue-freshness.py`), and a default Codex install has no
  `mcp__filesystem__` server — so `Bash cat` (the *only* real default-install read path) is
  completely unguarded by this gate. Set `action_enforced: false` for
  `repeated_read_search:codex:0.144.6` to reflect that honestly, matching the precedent already
  set by `noisy_command_output:codex`.
- Installed less_tokens into a disposable temp repo for the capture. `install.py`'s Codex
  version-scan unconditionally checks `/Applications/ChatGPT.app`'s bundled Codex (0.145.0,
  outside the verified contract range) even when only testing the PATH `codex-cli 0.144.6` —
  worked around by monkeypatching `detect_codex_releases` in-process rather than touching
  `/Applications`. If that ChatGPT.app Codex build ever gets upgraded into range, this workaround
  becomes unnecessary.
- Tightened (not rewrote) `BACKLOG.md`'s HP1 row per the "delete only when actually done" rule.

## Open work

Only `edit_verification` and `verbose_final_response` (both agents) remain for HP1:
1. `edit_verification` — needs a real Edit/Write plus read-after-edit/post-edit-diff probe.
2. `verbose_final_response` — needs an unmodified-vs-terse Stop-response baseline diff.

Once all 14 cells are `measured`, delete HP1's `BACKLOG.md` row per the "delete only when actually
done" rule and add a closing `CHANGELOG.md` entry.

## Suggested skills

- `continue` — when handing off again.
- `less-tokens` — targeted exploration of the hook/budget code before extending captures.

## Start here

Pick `edit_verification` or `verbose_final_response` next. For Codex captures needing a disposable
install, remember the `ChatGPT.app` version-gate workaround above, and remember `context-cache.py`'s
PreToolUse/PostToolUse recording split in case similar record-then-check plumbing exists for
edit-verification hooks (`read-after-edit.py`/`post-edit-diff.py`).

---
_Last updated at HEAD `7bd4829` on 2026-07-22._
