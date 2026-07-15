# Bug-Hunt Protocol

Full protocol lives in the shared canonical source:

**[agents/common/bug-hunt-protocol.md](../../../../agents/common/bug-hunt-protocol.md)**

Read that file for the severity rubric, three signals, stop rule, and agent prompt template.

Hunt log: [bughuntlog.jsonl](bughuntlog.jsonl) — validate, append, and score a round with
`.claude/tools/hunt_round.py`; re-score without appending with `.claude/tools/hunt_score.py`
