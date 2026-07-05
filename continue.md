# Continue: less_tokens

> **Next focus:** `BACKLOG.md`'s new "Same-session `search.py` repeated-query cache" item is
> instrument-first, same as the compaction-threshold and cache-gate items below — none of them
> are actionable again until real `near_misses.jsonl` data accumulates from normal use. Otherwise,
> `stats.py --calibrate` (Strategy 1) just needs a session with `ANTHROPIC_API_KEY` present.

## Current state
`eb_plan_4jul26.md`'s execution is **done** for this pass. Graphify investigation is closed (see
`eb_eval_4jul26.md`, `eb_plan_4jul26.md`, and `BACKLOG.md`'s "Decided against" section — do not
re-open unless graphify ships a Gemini-only build mode this repo can hard-gate to). 897/897 tests
pass (`pytest .claude/tests/unit/ .claude/tests/integration/`); both CI gates
(`changelog_gate.py`, `label_consistency_gate.py`) pass clean. Repo has uncommitted changes from
this session — nothing has been committed or pushed.

Three documents now live at repo root as the team-review + execution record: `eb_eval_4jul26.md`
(effectiveness evaluation, real telemetry-backed), `eb_plan_4jul26.md` (phased plan, updated
in-place with an execution note on Strategy 2 Phase C where the plan needed a real design
correction), and this file.

## What happened this session
- Ran a team review (`tect` + `qa`) evaluating every shipped token-reduction strategy against real
  telemetry — wrote `eb_eval_4jul26.md`. Ruled reject on graphify (default build path spends real
  Claude-subagent tokens, inverting the repo's mission).
- Ran a second team pass (`backend` + `qa`) to work up an implementation plan — wrote
  `eb_plan_4jul26.md`.
- Executed the plan:
  1. **Strategy 2 — fixed the v2 budget-plane contamination bug.** `events_path(root)`
     (`agents/common/budget/events.py`) ignored `LESS_TOKENS_STATE_DIR`; added
     `resolve_state_root()` (`agents/common/budget/state.py`), threaded it through
     `budget_hook_outcome` (config stays repo-relative; state does not), and fixed the same bug in
     `.less_tokens/tools/budget_report.py`/`budget_doctor.py`. Added a CI-blocking isolation
     regression test (`test_hooks_state_dir.py::TestBudgetObserverStateDirIsolation`) plus a
     general `_no_production_telemetry_writes` session fixture in `.claude/tests/conftest.py`
     (watches `.less_tokens/state/events.jsonl` specifically — deliberately *not*
     `savings.jsonl`, since `test_hooks_protocol.py` already grows that one on purpose, an
     accepted pre-existing pattern, not a leak).
  2. **Strategy 2 Phase C — the plan's literal "flip one config value" didn't match the code**:
     `mode` was global-only, `unscored_context`'s hard-cap check was hardcoded to `strict`. Built
     the missing primitive instead — `BudgetConfig.category_modes`/`effective_mode()`, threaded
     through `gate.py` and `advice.py` — so `unscored_context` alone now runs at `advise` while
     everything else stays on the untouched global `observe`. See `eb_plan_4jul26.md`'s Phase C
     note for the full design record.
  3. **Cross-cutting quantification framework** — `stats.py --audit-liveness` (manual/periodic,
     not CI — CI has no production telemetry to check against) and `label_consistency_gate.py`
     (CI-blocking, modeled on `changelog_gate.py`; fixed the two README claims it would have
     failed on — Terse output mode, Lean tool output — by adding honesty markers).
  4. **Strategy 3/4 Phase 0** — near-miss instrumentation (`near_misses.jsonl`) for cached-bash,
     cached-grep, and the compaction-trigger's transcript-size distribution. Additive only, no
     hook behavior changed.
  5. **Strategy 5** — corrected `DOCUMENTATION.md`'s prior "query/result cache" rejection (it
     conflated embedding-compute savings with context-token savings) and opened a properly scoped,
     instrument-first follow-up in `BACKLOG.md`.
  6. **Strategy 1 (calibration)** — blocked, no `ANTHROPIC_API_KEY` in this environment.
- Along the way: found and out-of-scope-flagged (via `spawn_task`, not fixed here) that
  `test_hooks_protocol.py` also grows real `.claude/state/savings.jsonl` on every run — a
  pre-existing, separate issue from the one fixed above.
- Repeatedly caught my own test runs contaminating real `.claude/state/savings.jsonl` /
  `.less_tokens/state/events.jsonl` mid-session; restored both to the exact byte count
  `eb_eval_4jul26.md` originally documented (264 / 160 lines) each time before proceeding.

## Open work
1. **Strategy 1 — calibrate the token estimate.** Run `stats.py --calibrate` once
   `ANTHROPIC_API_KEY` is available. Zero behavior risk, just needs the key.
2. **Strategy 3 Phase 1-2 / Strategy 4's threshold decision / the new search.py-cache item** —
   all explicitly wait for real `near_misses.jsonl` data to accumulate from normal use before any
   further code change. Do not guess at the numbers; that's the mistake this pass was fixing.
3. **Separately flagged, not part of this plan**: fix `test_hooks_protocol.py`'s real
   `savings.jsonl` growth (`task_1b13bd51` if still live — check before re-flagging).
4. Nothing to commit unless the user asks — this session made no commits.

## Suggested skills
- `/bugfix` if a `near_misses.jsonl` review later turns into an atomic fix.
- `/continue` — update this handoff again once calibration runs or the near-miss data is reviewed.

## Start here
Check `.claude/state/near_misses.jsonl` for accumulated real usage data before touching Strategy
3/4/5 again — that data not existing yet is *why* those items are open, not a gap to fill by
guessing. `eb_plan_4jul26.md` has exact file/line references for everything already shipped.

---
_Last updated at HEAD `45e2e27` (plus uncommitted session changes) on 2026-07-04, after executing
`eb_plan_4jul26.md`._
