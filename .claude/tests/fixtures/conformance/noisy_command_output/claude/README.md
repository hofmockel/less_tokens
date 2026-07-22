# `noisy_command_output` — Claude bounded live capture

Captured 2026-07-21 in this dogfooded repo's own live Claude Code session.

## Method

A `Bash` command (`cat`-ing several multi-hundred-line docs/decision files together) returned a
combined output far larger than any single task-relevant portion. `truncate-output.py`'s
`PostToolUse:Bash` hook capped the model-visible result.

## Results

| Probe | Total output | Model-visible after truncation | Elided |
| --- | ---: | ---: | ---: |
| Combined `cat` of `DECISIONS.md` tail + `.claude/tests/unit/test_hook_manifest_parity.py` | 25,336 chars | 5,032 chars | 20,304 chars (~80%) |

The figure is the literal `[truncated — N chars omitted (M total)]` annotation attached to that
specific tool result in this session's transcript — not a `savings.jsonl` aggregate. `savings.jsonl`
is a shared, non-session-scoped log (generic `session_id: "local-session"`, entries from other
processes/runs interleaved), so it was deliberately not used to back this claim; see
`reports/runs/2026-07-21-hp1-conformance-matrix/report.md` for why.

`event_fired: true`, `action_enforced: true`, `basis: measured` for
`noisy_command_output:claude:2026-07-21`.
