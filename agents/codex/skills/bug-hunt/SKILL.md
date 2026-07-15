---
name: bug-hunt
description: Run a structured bug hunt via the shared protocol. Use to find bugs, run a hunt round, or apply the stop rule.
---

# Bug-Hunt Protocol

Full protocol lives in the shared canonical source:

**[agents/common/bug-hunt-protocol.md](../../common/bug-hunt-protocol.md)**

Read that file for the severity rubric, three signals, stop rule, and agent prompt template.

Hunt log: `.claude/skills/bug-hunt/bughuntlog.jsonl` — validate, append, and score a round with
`.claude/tools/hunt_round.py`; re-score without appending with `.claude/tools/hunt_score.py`
