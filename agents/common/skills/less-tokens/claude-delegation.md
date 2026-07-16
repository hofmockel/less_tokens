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
