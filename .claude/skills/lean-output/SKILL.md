---
name: lean-output
description: Pipe noisy CLI tool output through signal-only parsers (pytest, ruff, eslint, git). Use when a Bash command dumps large test/lint/diff output and you only need the failures and counts.
---

# lean-output — structured parsers

The `lean-output.py` PostToolUse hook fires automatically on recognized Bash commands. To parse manually:

    .claude/bin/python .claude/tools/parse.py pytest  < output.txt
    .claude/bin/python .claude/tools/parse.py ruff    < output.txt
    .claude/bin/python .claude/tools/parse.py git     < output.txt
    .claude/bin/python .claude/tools/parse.py eslint  < output.txt

Parsers keep the signal:
- **pytest** — FAILED/ERROR lines + assertion (`E …`) lines + summary
- **ruff** — `file:line:col: CODE message` rows + summary
- **git** — name-status rows, `--stat` lines, summary line
- **eslint** — error/warning lines + summary
