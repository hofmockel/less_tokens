# Continue: less_tokens

> **Next focus:** nothing blocked on engineering right now — pick up BACKLOG.md's next open item.

## Current state
HEAD is `8b49e83`, working tree clean, pushed to `origin/main`.

## What happened this session
- Picked "Generate README strategy table from a strategy registry" off BACKLOG.md (Prose to
  Code / Token-Reduction Strategies section). Added `.claude/tools/strategy_registry.py` as the
  single source of the 8 strategy rows (name/how/savings/flag/telemetry key); `README.md`'s
  strategy table now renders from it via `.claude/tools/strategy_table_docs.py --check`
  (mirrors `hook_parity_docs.py`'s marker pattern), and `label_consistency_gate.py` derives its
  README-name → telemetry-key map from the same registry instead of a hardcoded dict. Wired
  `strategy_table_docs.py --check` into `.pre-commit-config.yaml` and `.github/workflows/tests.yml`.
  BACKLOG.md row removed — shipped.
- Cache-key widening for bash/grep (the other High Priority BACKLOG row) was checked and is
  still blocked: `.less_tokens/state/near_misses.jsonl` and `.claude/state/near_misses.jsonl`
  have zero `"bash"`-kind entries, and no `.codex/state/` directory exists yet. Do not widen the
  allowlist blind — wait for real Codex-side near-miss data to accumulate first.
- Full unit suite: 834 passed, same 13 pre-existing unrelated failures (toolcost/stats/
  agentsmd-budget token-calibration tests) — unchanged by this session's changes.

## Open work
See [BACKLOG.md](BACKLOG.md) for the current list. Notable: installer deployment-spec
duplication (`install.py` mirrors `_install_specs()` and `main()` by hand), bug-hunt protocol
data-driven conversion, and several Medium prose-to-code/doc-drift items. Cache-key widening
stays parked until Codex-side `"bash"`-kind near-miss data actually shows up.

## Suggested skills
- `/bugfix` or a BACKLOG.md prose-to-code row — no bugs currently filed in the Bugs table.

## Start here
Check BACKLOG.md's remaining High Priority rows (Installer / Prose to Code sections) for the
next pick.

---
_Last updated on 2026-07-14, HEAD `8b49e83` (working tree clean, pushed)._
