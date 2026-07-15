# Continue: less_tokens

> **Next focus:** nothing blocked on engineering right now — pick up BACKLOG.md's next open item.

## Current state
HEAD is `73ddc3c`, working tree clean, pushed to `origin/main`.

## What happened this session
- Picked "Make bug-hunt protocol data-driven" off BACKLOG.md (Prose to Code / High Priority).
  `agents/common/bug-hunt-protocol.md`'s severity tiers, target-file list, thresholds, and prompt
  template were hand-maintained prose that had drifted from `hunt_score.py`'s hardcoded
  `TARGET_FILES` — the doc's 14-file list and the scorer's 14-file set shared only 10 real
  entries; each side named files that don't exist on disk.
- Added `.claude/tools/bug_hunt_registry.py` as the single source (`SEVERITY_TIERS`, a corrected
  15-file `TARGET_FILES`, `OVERLAP_THRESHOLD`/`COVERAGE_THRESHOLD`, `PROMPT_TEMPLATE`,
  `ROUND_REQUIRED_KEYS`). `hunt_score.py` now imports from it instead of hardcoding. Added
  `.claude/tools/bug_hunt_docs.py` to render/verify the protocol doc's four generated blocks
  (mirrors `strategy_table_docs.py`'s marker pattern) and wired `--check` into pre-commit. Added
  `.claude/tools/hunt_round.py`, replacing the doc's hand-done "(3) append JSON, (4) run
  hunt_score.py" operator steps with one command that validates a round record before appending
  and scoring; dropped a dead `cumulative_files` schema field nothing ever read.
- New tests: `test_bug_hunt_docs.py`, `test_hunt_score.py`, `test_hunt_round.py` (31 cases).
  Documented the new registry/docs/round tools in `DOCUMENTATION.md`'s Skills section (they were
  previously undocumented, same as `strategy_registry.py`/`strategy_table_docs.py` from the prior
  session). BACKLOG.md row removed — shipped.
- Full unit + integration suite green aside from the same 13 pre-existing unrelated failures
  (toolcost/stats/agentsmd-budget token-calibration tests).

## Open work
See [BACKLOG.md](BACKLOG.md) for the current list. Notable Medium-priority prose-to-code/doc-drift
items: generate installer flag docs from argparse metadata, skill manual generation, subagent
guidance split, parity-doc generation, dev command shim, canonical-home rules. Cache-key widening
for bash/grep stays parked until Codex-side `"bash"`-kind near-miss data actually shows up in
`.less_tokens/state/near_misses.jsonl`.

## Suggested skills
- `/bugfix` or a BACKLOG.md prose-to-code row — no bugs currently filed in the Bugs table.

## Start here
Pick a Medium-priority prose-to-code/doc-drift item off BACKLOG.md — no High Priority rows remain
open.

---
_Last updated on 2026-07-14, HEAD `73ddc3c` (working tree clean, pushed)._
