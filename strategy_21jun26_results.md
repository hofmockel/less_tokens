# Strategy 21 Jun 2026 Results

This records the implementation outcome for `strategy_21jun26_plan.md`.

## What Shipped

- Added `agents/common/budget/` as the shared budget engine for Claude and Codex.
- Added `.less_tokens/config/budget.json` with `observe`, `advise`, `enforce`, and `strict` modes.
- Wired Claude and Codex budget observer hooks through the shared engine.
- Added v2 budget telemetry at `.less_tokens/state/events.jsonl`.
- Added `.less_tokens/tools/budget_report.py` and `.less_tokens/tools/budget_doctor.py`.
- Added relevance scoring from explicit paths, search ranges, stack traces, grep/search cache, and recent edits.
- Added replacement/block decisions for broad reads, repeated reads/searches, broad listings, oversized tool output, and oversized unscored context.
- Added pressure-based compaction snapshots with per-agent session files.
- Updated installer checks and runtime deployment for the shared `.less_tokens/` control plane.
- Updated README, reference docs, changelog, and Codex hook coverage docs.

## Verification

Commands run during the final chunks:

```bash
.claude/.venv-tokens/bin/python -m pytest .claude/tests/unit/test_budget_core.py .claude/tests/unit/test_budget_observer.py .claude/tests/unit/test_budget_docs.py
.claude/.venv-tokens/bin/python -m pytest .claude/tests/unit .claude/tests/integration
.claude/.venv-tokens/bin/python .less_tokens/tools/budget_report.py
.claude/.venv-tokens/bin/python .less_tokens/tools/budget_doctor.py
```

Results:

- Budget-focused tests: 29 passed.
- Full unit and integration suite: 699 passed.
- `budget_report.py`: ran successfully; no live v2 telemetry had been recorded in this checkout yet.
- `budget_doctor.py`: ran successfully; default mode was `observe`, with no recent pressure, decisions, compactions, or quality risk recorded.

## Acceptance Status

| Phase | Status | Evidence |
|---|---|---|
| Phase 1: New core and telemetry | Complete | Shared budget package, default config, report tool, observer hooks, installer checks, v2 event tests |
| Phase 2: Relevance gate | Complete | Tests cover explicit path, search ranges, failure paths, recent edits, and equivalent normalized payloads |
| Phase 3: Advise mode | Complete | Advice is mode-gated, capped at 600 chars, and doctor output is tested |
| Phase 4: Enforce mode | Complete | Tests cover repeated reads/searches, broad listings, strict unscored context, and bypass behavior |
| Phase 5: Dynamic output summaries | Complete | Tests preserve pytest failure signal while shrinking noisy output |
| Phase 6: Pressure-based compaction | Complete | Tests verify pressure trigger, compact snapshot budget fit, and per-agent session state |
| Phase 7: Installer and docs redesign | Complete | Installer tests pass; README, documentation, changelog, and Codex coverage docs updated |

## Dogfooding Notes

- The current repo is installed with `.less_tokens/config/budget.json` in `observe` mode, which is the safest default for rollout.
- Report and doctor tools work in the repo before any telemetry exists, which gives a clean first-run experience.
- Live savings numbers require actual hook-delivered events in `.less_tokens/state/events.jsonl`; this checkout had no persistent events at the time of the final verification run.
- The next useful dogfood step is to switch a scratch install to `advise` for one normal coding session, then review `budget_report.py` for noisy suggestions before trying `enforce`.
