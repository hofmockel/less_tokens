---
name: less-tokens
description: Token-efficient codebase exploration for Claude. Use to search the codebase, look up a symbol, check a file before reading, audit CLAUDE.md size, or decide whether to spawn a subagent.
---

## less-tokens — Token-Efficient Codebase Exploration

Shared vector search and guard tools installed in `.claude/tools/`. CLAUDE.md keeps only terse rules; load this skill when you need the concrete commands.

### Search before reading

    .claude/.venv-tokens/bin/python .claude/tools/search.py "query"

Returns the top matching chunks by semantic similarity. Run this before a whole-file Read on any large or indexed file.

### Symbol lookup

    .claude/.venv-tokens/bin/python .claude/tools/symbols.py SymbolName

Returns exact `file:line` for Python and JS/TS functions, classes, constants, and types. Cheaper than grep for definitions.

### Noise-file guard

    .claude/.venv-tokens/bin/python .claude/tools/read_guard.py path/to/file

Checks whether the file is a lockfile, generated bundle, binary, or large data file. Returns a recommendation before you commit to reading it in full.

### CLAUDE.md audit

    .claude/.venv-tokens/bin/python .claude/tools/claudemd_audit.py

Checks CLAUDE.md token budget, stale line references, and verbosity. Run before adding new sections.

### Directory navigation and responses

Prefer `rg --files` over `find . -R` or `ls -R`. Keep replies to direct findings with exact `file:line` references and no filler.

### Delegated Claude work

Use the Agent tool only when the user explicitly asks for subagents, delegation, or
parallel work — a spawned child pays a full fixed startup tax (system prompt +
CLAUDE.md + tool schemas) with no transcript copy, so only spawn when the tokens
it discards exceed that tax. Skip spawning for a single Read/Grep, one small file
check, or a short test command.

Prefer the narrow agent-definition files this skill installs over the generic
`general-purpose` agent when the task fits:

- `explorer` (`.claude/agents/explorer.md`, Read/Grep/Glob only) — messy "find
  where X is wired" searches. Route these here so the dead ends and false starts
  stay in the child's window; only the conclusion returns.
- `verifier` (`.claude/agents/verifier.md`, Bash/Read only) — noisy test/lint/build
  loops. Route these here so the log spam stays in the child; only pass/fail and
  the failing line return.

A narrower `tools:` allowlist means fewer tool schemas loaded per child — the
per-agent fixed-cost lever. Use `general-purpose` (or a specialized agent type,
if the host repo defines one) only when the task needs tools neither of the above
allows.

Required return shape from any spawned agent: `files changed`, `findings`,
`verification`, `blockers`. Reject pasted file bodies, full logs, and full diffs
in the response — ask for exact `file:line` references instead.

Prompt shape:

    Task: answer <specific question>.
    Context pointers: <path:line>, search query "<query>", run <command if needed>.
    Constraints: do not paste full files; do not revert unrelated edits.
    Return only: files changed, findings, verification, blockers.

Parallel dispatch checklist:

    Spawn only independent tasks that can finish without sharing context.
    Use explorer for read-only questions; use verifier for test/lint/build loops.
    While agents run, continue local work that does not overlap their task.

Subagent output contract:

    files changed: <paths or none>
    findings: <file:line bullets only>
    verification: <commands or checks run>
    blockers: <none or concrete blocker>

Noisy verification delegation:

    Task: run <test/lint/build command> and summarize only failures.
    Constraints: do not edit files; do not paste full logs.
    Return only: pass/fail, failing command, top failure cause, file:line refs, blockers.

Use this only when the verification loop is likely to emit noisy output and the
parent can continue non-overlapping work while the child runs. Keep short checks
local; the child startup cost is not worth moving a quick command.

Context pack shape for spawned agents:

    Objective: <one bounded result>.
    Start with: .claude/.venv-tokens/bin/python .claude/tools/search.py "<query>"
    Pointers: <path:line>, <path:line>.
    Allowed reads: only slices needed to answer the objective.
    Return only: file:line findings, verification, blockers.

Do not paste source bodies, diffs, logs, or previous search output into a spawn
prompt. Pass the query and pointers so the child pays only for the slices it
chooses to inspect.

Large-source digest delegation:

    Task: summarize <source path> into .claude/state/<name>.md.
    Constraints: parent must not read the source first.
    Return only: digest path, source path, line refs used, verification, blockers.

Use this for one-off large docs or logs where the parent only needs the distilled
answer. The digest should be short, source-linked, and agent-neutral so another
Claude or Codex session can verify it without re-reading the whole source.

### Document-draft exemption

Terse mode holds for ordinary replies only. If the user's message asked for a document, report,
or proposal draft and you're pasting it directly in your reply (not a file write, not fenced),
include this exact line anywhere in the response:

    <!-- less-tokens: document-draft -->

`caveman-reminder.py` detects it and skips the word cap and filler check for that response. Set it
only because the user's message asked for a document — never on your own judgment that a
response is long or important.

### Rebuild the index

    .claude/.venv-tokens/bin/python .claude/tools/embeddings.py refresh

Re-embeds any source files that changed since the last index build.
