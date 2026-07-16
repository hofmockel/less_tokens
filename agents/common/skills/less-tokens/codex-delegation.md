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
