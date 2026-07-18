# Continue: less_tokens

> **Next focus:** merge PR #82, then pick up CX25 (Bash-command read detection) or CX19 (now unblocked).

## Current state
`main` is at `928b300` (PR #81 merged: filed CX24, blocked CX19). Working branch
`fix/cx24-filesystem-tool-name-mismatch` (HEAD `7afd7e8`) has PR
[#82](https://github.com/hofmockel/less_tokens/pull/82) open, pushed, CI status unconfirmed at
write time. Working tree clean.

## What happened this session
- Merged PR #81 (filed CX24, blocked CX19).
- Investigated CX24 live: confirmed `mcp__filesystem__.*` **is** a real Codex matcher — but only
  when a user explicitly configures an MCP server literally named `filesystem`
  (`@modelcontextprotocol/server-filesystem`, live-tested against `codex-cli 0.142.3`). A default
  install has no such server (reconfirms last session's finding).
- Found a second, deeper bug while probing: the live server's read tool is named
  `read_text_file`, not `read_file` — every consumer (`_codex_runtime.py`, `read-guard.py`,
  `truncate-output.py`, `truncate_output.py`, `install.py`'s smoke check) hardcoded only the old
  name, so even the intended opt-in path silently no-op'd. Fixed by accepting both names.
  `dev.py unit` (944 passed).
- Filed **CX25**: the larger, separate gap — these 6 hooks have no `Bash` fallback, so they stay
  dead in a default install. Needs real design work (safely parsing read-shaped Bash commands),
  explicitly scoped out of this session by user direction. `BACKLOG.md`/`CHANGELOG.md` updated;
  CX19 unblocked (no longer depends on CX24).

## Open work
See [BACKLOG.md](BACKLOG.md). Ready-now order: **CX25** (new, P0, Research) → **CX19** (P1,
unblocked) → CN1.

## Suggested skills
- None specific — CX25 is a design/research task (parsing Bash commands safely), not a
  bugfix/bug-hunt fit until the approach is settled.

## Start here
Run `gh pr checks 82`; merge if green. Then start CX25: decide which Bash command shapes
(`cat`, `head -n`, `sed -n`, etc.) count as a "read" for each of the 6 affected hooks, and how to
safely extract path/offset from them.

---
_Last updated at HEAD `7afd7e8` (PR #82 open on `fix/cx24-filesystem-tool-name-mismatch`, CI status unconfirmed at write time) on 2026-07-18._
