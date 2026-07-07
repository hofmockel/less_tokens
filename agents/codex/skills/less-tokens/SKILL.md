---
name: less-tokens
description: Token-efficient codebase exploration for Codex. Use to search the codebase, look up a symbol, check a file before reading, or audit AGENTS.md size.
---

## less-tokens — Token-Efficient Codebase Exploration

Shared vector search and guard tools installed in `.less_tokens/`. AGENTS.md keeps only terse rules; load this skill when you need the concrete commands.

### Search before reading

    .less_tokens/bin/python .less_tokens/tools/search.py "query"

Returns the top matching chunks by semantic similarity. Run this before a whole-file Read on any large or indexed file.

### Symbol lookup

    .less_tokens/bin/python .less_tokens/tools/symbols.py SymbolName

Returns exact `file:line` for Python and JS/TS functions, classes, constants, and types. Cheaper than grep for definitions.

### Noise-file guard

    .less_tokens/bin/python .less_tokens/tools/read_guard.py path/to/file

Checks whether the file is a lockfile, generated bundle, binary, or large data file. Returns a recommendation before you commit to reading it in full.

### AGENTS.md audit

    .less_tokens/bin/python .less_tokens/tools/agentsmd_audit.py

Checks AGENTS.md token budget, stale line references, and verbosity. Run before adding new sections.

### Directory navigation and responses

Prefer `rg --files` over `find . -R` or `ls -R`. Keep replies to direct findings with exact `file:line` references and no filler.

### Delegated Codex work

Use Codex subagents only when the user explicitly asks for delegation, subagents,
or parallel work. Default to `fork_context=false`; pass pointers, search queries,
and commands instead of pasted files. Use `explorer` for read-only questions and
`worker` only for disjoint file ownership. Tell workers not to revert unrelated
edits. Require the return shape: `files changed`, `findings`, `verification`,
`blockers`. Close completed agents.

Skip spawning for a single `rg`, one small file read, or a short test command.
Consider it for independent exploration, noisy verification loops, or large-source
summaries where discarded child context is worth the startup cost. Use
`fork_context=true` only when the child truly needs prior conversation; a manual
Codex comparison on 2026-07-05 found the full-history fork did extra discovery on
a task the cold `fork_context=false` explorer answered from pointers alone.

Prompt shape:

    Task: answer <specific question>.
    Context pointers: <path:line>, search query "<query>", run <command if needed>.
    Constraints: fork_context=false; do not paste full files; do not revert unrelated edits.
    Return only: files changed, findings, verification, blockers.

Parallel dispatch checklist:

    Spawn only independent tasks that can finish without sharing context.
    Use explorer for read-only questions; use worker only with disjoint file ownership.
    Keep fork_context=false unless prior conversation is required.
    While agents run, continue local work that does not overlap their task.
    Close every completed agent after collecting the result.

Subagent output contract:

    files changed: <paths or none>
    findings: <file:line bullets only>
    verification: <commands or checks run>
    blockers: <none or concrete blocker>

Reject pasted file bodies, long logs, full diffs, broad summaries, and speculative
next steps. Ask for exact line references when a child reports a code finding.

Noisy verification delegation:

    Task: run <test/lint/build command> and summarize only failures.
    Constraints: fork_context=false; do not edit files; do not paste full logs.
    Return only: pass/fail, failing command, top failure cause, file:line refs, blockers.

Use this only when the verification loop is likely to emit noisy output and the
parent can continue non-overlapping work while the child runs. Keep short
checks local; the child startup cost is not worth moving a quick command.

Context pack shape for spawned agents:

    Objective: <one bounded result>.
    Start with: .less_tokens/bin/python .less_tokens/tools/search.py "<query>"
    Pointers: <path:line>, <path:line>.
    Allowed reads: only slices needed to answer the objective.
    Return only: file:line findings, verification, blockers.

Do not paste source bodies, diffs, logs, or previous search output into a spawn
prompt. Pass the query and pointers so the child pays only for the slices it
chooses to inspect.

### Document-draft exemption

Terse mode holds for ordinary replies only. If the user's message asked for a document, report,
or proposal draft and you're pasting it directly in your reply (not a file write, not fenced),
include this exact line anywhere in the response:

    <!-- less-tokens: document-draft -->

`terse-reminder.py` detects it and skips the word cap and filler check for that response. Set it
only because the user's message asked for a document — never on your own judgment that a
response is long or important.

### Rebuild the index

    .less_tokens/bin/python .less_tokens/tools/embeddings.py refresh

Re-embeds any source files that changed since the last index build.
