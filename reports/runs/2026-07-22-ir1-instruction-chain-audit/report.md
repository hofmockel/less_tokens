# IR1 — Audit the complete instruction chain, not only one root file

Date: 2026-07-22

## Method

`claudemd_audit.py`/`agentsmd_audit.py` only ever measured a single passed-in root file, and
`--rules` only globbed top-level `.claude/rules/*.md` non-recursively with no scoping awareness.
Before writing a fix, verified the actual platform mechanics against primary sources rather than
assuming the backlog item's own description was complete:

- Fetched `https://code.claude.com/docs/en/memory` (Anthropic, fetched 2026-07-22) for CLAUDE.md
  discovery order, `.claude/rules/` recursive discovery and `paths:` scoping, user vs project rule
  precedence, and the auto-memory `MEMORY.md` 200-line/25KB startup bound.
- Fetched `https://developers.openai.com/codex/guides/agents-md` (redirects to
  `learn.chatgpt.com/docs/agent-configuration/agents-md`, OpenAI, fetched 2026-07-22) for Codex's
  `AGENTS.override.md` → `AGENTS.md` → fallback-filename precedence, root-down concatenation
  order, and `project_doc_max_bytes` (default 32 KiB) stop-adding-files behavior.
- Found and read `github.com/anthropics/claude-code/issues/17204`: a community report (no
  maintainer confirmation, no version pinned) that quoted/YAML-list `paths:` frontmatter silently
  fails to scope a rule, while unquoted `paths:` and the undocumented `globs:` key both work.

## What shipped

`.claude/tools/instruction_chain_audit.py` (`--agent claude|codex [--cwd PATH] [--json]`):

- **Claude**: walks the CLAUDE.md/CLAUDE.local.md ancestor chain root-to-cwd, recursively
  discovers `.claude/rules/**/*.md` (top-level unscoped rules = fixed; path-scoped rules, nested
  `.claude/rules/` dirs, and subdirectory CLAUDE.md = on-demand), includes user-level
  (`~/.claude/CLAUDE.md`, `~/.claude/rules/`) and best-effort managed-policy locations, and reports
  the auto-memory `MEMORY.md` startup-loaded token count (first 200 lines / 25KB, whichever first)
  **without ever reading or printing its content beyond that bound**. Splits total into fixed
  (every-turn tax) vs on-demand tokens.
- **Codex**: models the `AGENTS.override.md` → `AGENTS.md` → `project_doc_fallback_filenames`
  precedence per directory from git-root down to cwd, plus the global `~/.codex/` pair, reads
  `project_doc_max_bytes` from `~/.codex/config.toml` (defaults to 32768), and reports which files
  were included vs skipped once the cumulative byte budget was reached.
- Flags each rule using disputed `paths:`-only frontmatter (cites #17204) rather than assuming it
  either works or is broken.
- Heuristically flags unscoped rules whose prose reads path-specific (≥2 distinct
  extension/directory hints) as path-scoping candidates — a hint, not a verdict, same spirit as
  `claudemd_audit.py`'s existing `verdict()`.

Tests: `.claude/tests/unit/test_instruction_chain_audit.py`, 7 cases covering nested CLAUDE.md,
scoped-vs-unscoped rules, nested rules dirs, the disputed-`paths:` flag, the path-scoping-candidate
heuristic, `MEMORY.md` over-limit detection, and Codex override/fallback/budget-skip. `dev.py unit`:
1125 passed, no regressions.

## Modeling assumptions not verified live (flagged in the tool's own docstring, not hidden)

1. Whether the Codex file that pushes cumulative size *over* `project_doc_max_bytes` is excluded
   in full (assumed here) or partially truncated — the docs say "stops adding files" and "doesn't
   truncate existing ones" but don't state which side of the boundary the crossing file lands on.
2. The exact auto-memory directory slug algorithm (`~/.claude/projects/<slug>/memory/`) is inferred
   from observed directory names on disk, not published.
3. The `paths:` frontmatter reliability report (#17204) is unconfirmed by a maintainer and carries
   no version number — treated as a flag to surface, not a fact to hard-code.

None of these need to block shipping a reporting tool; they're each a candidate one-line follow-up
research item if someone wants them nailed down with a live probe (CX26-style), not IR1's job.

## Outcome

Accepted — tool ships, recorded in `DECISIONS.md`. `.less_tokens/tools/instruction_chain_audit.py`
Codex shim generated directly via `install._codex_tool_shim_text()` rather than through
`install.py --self-refresh --agent codex`, because the installed local Codex (`0.145.0`) is outside
the CX32-tracked verified hook window (`0.142.3–0.144.6`) and `install.py` refuses to wire Codex
adapters outside it. The shim itself is static/deterministic (just re-execs the `.claude/tools/`
source) and carries no hook-wiring risk, so generating it directly was safe; re-run
`install.py --self-refresh --agent codex` for real once CX32 widens the window, to confirm the
installer's own path produces byte-identical output.
