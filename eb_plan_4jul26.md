# less_tokens Improvement Plan — 2026-07-04

Follow-up to `eb_eval_4jul26.md`. That review found what's working, what's dormant, and rejected
graphify. This plan works up *how* to act on it: a reusable, data-driven way to quantify every
strategy over time (feeding into the test suite, not a one-off audit), plus a phased plan for each
of the five strategies the eval proposed. Team: `backend` designed the fixes and the
quantification engine; `qa` designed how the test suite enforces it; this document is the
synthesis, including one ruling where the two disagreed.

Graphify is closed — see `BACKLOG.md`'s "Decided against" section (ruling recorded, the two open
Developer-Experience items deleted). Not revisited here.

## Cross-cutting: the quantification framework

The goal is a strategy registry that answers, per strategy ID, the same four questions
consistently, reusable by every future review instead of a fresh manual audit:

- Is it wired (hook file exists, imports clean)?
- Has it fired for real, in real telemetry, in a recent window?
- What's its measured-vs-upper-bound split?
- Is its real-world firing rate consistent with its *expected* frequency class?

That last question is the one this review needed twice (cached-grep/bash at zero events; the
entire v2 budget-plane log being test contamination) and nothing currently catches automatically.

**Data model** (`backend`'s design, adopted as-is): a small registry —
`STRATEGIES: dict[str, StrategySpec]` — naming each strategy's telemetry source
(`savings.jsonl` category or `events.jsonl` filter) and an `expected_frequency_class`:
`frequent` (should fire often — cached-grep/bash, truncation, search-first), `rare-but-real`
(fires occasionally by design — compaction), or `experimental` (new, no expectation yet). This
reuses `savings_log.py`'s existing `_KNOWN_STRATEGIES` as the canonical source rather than
duplicating it (`qa`'s grounding). The frequency class is a human judgment call recorded once per
strategy at registry-entry time, not inferred at runtime — that's what keeps "dormant" from being
either a fabricated statistical model or a silently-rotting hardcoded exemption list.

**Where the disagreement was, and the ruling:** `backend` proposed the liveness check as a
CI-blocking `tests/integration/test_strategy_liveness.py`. `qa` argued liveness is a property of
*production* telemetry accumulated over real sessions — a fresh CI checkout has no such history,
so a CI-blocking version of this test would necessarily assert against fabricated fixture data,
which is exactly what `stats_plan.md` already bans ("no test asserts a savings magnitude, because
magnitude is a property of real sessions, not of code"). **Ruling: qa is right, adopt qa's
invocation model.** The liveness check ships as a periodic/manual audit command
(`stats.py --audit-liveness`), not a pytest CI gate. What *is* legitimately CI-gated is the audit
tool's own classification *logic* against a hand-built fixture ("a strategy with 0 events in 90
days is flagged dead unless registered rare-but-real") — that tests code behavior, not production
reality, so it's a fair CI target. The 90-day window is a config constant, not a hardcoded value,
since this repo has no prior data to justify a specific number yet.

**Two things do belong in CI, unconditionally** (both `qa` proposals, both modeled on an existing
precedent in this repo rather than invented from scratch):

- **State-dir isolation regression test** — generalizes `test_hooks_state_dir.py`'s existing
  per-hook pattern into a blanket net. A session-scoped test snapshots every file under the real
  `.less_tokens/state/` and `.claude/state/` before the full suite runs, re-snapshots after, and
  fails on any new or modified file — naming exactly which one. This is what would have caught the
  budget-plane contamination *before* it happened, and it catches the same class of bug for any
  future hook, not just this one. Deterministic, no fixtures, can't be fabricated, can't be flaky.
- **Measured-vs-asserted label-consistency gate** — modeled directly on `changelog_gate.py`'s
  existing precedent (scan a doc, cross-reference an artifact, fail CI on drift, name the exact
  line). Scans `README.md`/`DOCUMENTATION.md` for percentage/magnitude claims near a strategy
  name; if the strategy has no row in the `savings_log.py` registry, the claim must carry an
  explicit "asserted only, not telemetry-backed" marker in the same paragraph, or CI fails. Also
  catches the reverse: a doc claiming "measured" for a strategy the registry tags `upper_bound`
  (guards the search-first / search-vs-full-read numbers specifically). This directly prevents the
  eval's finding #3 (terse-output's unbacked 30–60%) from recurring with the next strategy someone
  adds.

## Strategy 1 — Calibrate the token estimate

Cheapest, do first, no dependencies. `--calibrate` is already built, opt-in, network+key gated,
and has simply never been run (`state/calibration.json` doesn't exist anywhere in the repo).

- **Action:** run `.claude/tools/stats.py --calibrate` once against this repo's own code/prose
  sample.
- **Acceptance:** `state/calibration.json` exists with a dated divisor; `stats.py` output footer
  changes from `tokens est. at chars÷4 (uncalibrated)` to `chars÷N (calibrated <date>)`; every
  number in this document and the prior eval remains an estimate but a grounded one going forward.
- **Owner-facing note:** this doesn't change any behavior, only the honesty of the reported
  numbers — zero regression risk.

## Strategy 2 — Fix the v2 budget control plane

Root cause (already located, not re-derived): `events_path(root)`
(`agents/common/budget/events.py:81-82`) builds `root / ".less_tokens" / "state" / "events.jsonl"`
directly from the `repo` parameter threaded through `budget_hook_outcome()`
(`agents/common/hooks/budget_observer.py`) — it never consults `LESS_TOKENS_STATE_DIR`.
`.claude/tools/search_config.py:108-112`'s `active_state_dir()` already implements the correct
override-then-fallback pattern; `context_cache.py` already receives `state_dir` as an explicit
caller-supplied parameter instead of deriving it from repo root. The fix reuses that existing
pattern rather than inventing a new one.

- **Phase A — thread the fix.** New helper (parameterized version of `active_state_dir()`) resolves
  the state dir once inside `budget_hook_outcome`, before `load_budget_config`/
  `evaluate_budget_input` run. Change *what's passed as `root`* at the call sites, not
  `events_path`'s own signature — keeps the function pure and isolates the fix to callers. Audit
  `agents/common/budget/state.py`'s `should_emit_advice` in the same pass — same leak shape is
  plausible there and hasn't been checked yet.
- **Phase B — prove it, via the new CI-blocking isolation test above.** Contract tests that set
  `LESS_TOKENS_REPO=<real repo>` must no longer write to the real repo's `.less_tokens/state/`.
  This is the acceptance gate, not a spot-check grep — it's the general test described in the
  cross-cutting section, and this bug is exactly the case that motivates it.
- **Phase C — flip the mode, narrowly.** **Executed 2026-07-04, with a course-correction.** The
  plan assumed a per-category mode override already existed; it didn't — `mode` was global-only
  (`config.py`), and `unscored_context`'s hard-cap check was hardcoded to `strict` only
  (`gate.py`'s `_forced_decision`), so a literal "flip one JSON value" wasn't possible without
  changing behavior for every category. Built the missing primitive instead: a new
  `category_modes: dict[str, str]` config field (default `{}`, fully backward compatible),
  `BudgetConfig.effective_mode(category)` resolving per-category then falling back to the global
  mode, and `advice.py`'s `advice_for_mode`/`enforcement_decision`/`outcome_for_mode` now filter
  by each decision's own effective mode rather than one flat mode string. The unscored-context
  hard-cap decision is tagged with `category="unscored_context"` specifically (previously it
  inherited whatever category the underlying candidate had, which is never literally
  `"unscored_context"` — nothing would have matched a per-category key otherwise). Live config
  now has `"category_modes": {"unscored_context": "advise"}`; global `mode` stays `observe`
  untouched, and the advice rate-limit gate in `budget_observer.py` (previously gated on
  `config.mode == "advise"` specifically) was widened to fire on any advisory output regardless of
  source, so category-driven advice doesn't bypass rate-limiting. 876/876 tests pass, including a
  new regression test proving the category-only advice does *not* appear when
  `category_modes` is absent (preserving observe-mode silence for every other category).

## Strategy 3 — Expand the narrow cache gates (bash + grep)

Root cause (already located): `cacheable_bash_command()`
(`agents/common/hooks/context_cache.py:160-168`) classifies broadly by regex, but `check_bash`/
`record_bash` key the cache dict on the **exact full command string** — two semantically
equivalent invocations (`pytest tests/unit/foo.py -v` vs. the same file without `-v`) never
collide. `grep_key()` has the identical problem (verbatim join of pattern/path/glob/type/query).
Zero cached-bash or cached-grep events exist in 264 all-time telemetry events — this is the
concrete mechanism behind that zero.

- **Phase 0 — instrument before changing behavior.** Add a `near_misses.jsonl` log: when
  `cacheable_bash_command()`/`grep_key()` reject a repeat that *would* have hit under a normalized
  key, log `{"kind": "bash"|"grep", "raw": ..., "normalized": ...}`. Purely additive — no hook
  exit-code or message changes. This replaces guessing which flags/patterns to normalize with real
  data from this repo's own usage, the same "instrument, then act" discipline the eval already
  recommended.
- **Phase 1 — normalize the keys**, once Phase 0 has data: strip a documented allowlist of
  output-shape-neutral flags (`-v`, `--color`, etc. — the actual allowlist comes from Phase 0's
  observed near-misses, not a guess) before keying bash commands; for grep, hash
  `(pattern, path, glob, type)` post-normalization instead of a literal string join.
- **Phase 2 — split the TTL.** `check_context_cache` already accepts a separate `bash_ttl` param
  distinct from `grep_ttl` — that plumbing half-exists. Expose `CONTEXT_CACHE_BASH_TTL` as its own
  config value in `.claude/hooks/context-cache.py` (currently bash silently falls back to the grep
  TTL) so the two can be tuned independently once real firing data exists to tune against.
- **Acceptance:** the liveness audit (cross-cutting section) shows cached-bash/grep move from
  `frequent`-class-but-dormant to actually firing over a real session window. Unit tests cover only
  the normalization function's determinism (pure logic), never a savings magnitude.

## Strategy 4 — Investigate the compaction trigger threshold

Newly grounded this pass (not covered by the eval's original research): `MAX_SESSION_CHARS =
500_000` (`.claude/tools/search_config.py:90`, ~125k tokens, scaled per model), with a hysteresis
band of a quarter of that to avoid re-firing at the same size
(`agents/common/hooks/compact_trigger.py:23,52-53`). This is not obviously a bug — it's a
deliberately high bar, and most sessions simply never reach a 125k-token transcript before ending
naturally or being manually compacted. The single all-time firing (660,000 chars / ~165k tokens
saved) confirms the mechanism works correctly when the bar is cleared; it says nothing about
whether the bar is set well, because there's currently no data on how close *other* sessions come
without crossing it.

- **Action:** before touching the threshold, add near-miss instrumentation here too (same pattern
  as Strategy 3): log transcript size at the point of every hook invocation regardless of whether
  it crosses `MAX_SESSION_CHARS`, so the real distribution of session sizes becomes visible.
- **Then decide**, from real data: if many sessions cluster just under 500k chars, lowering the
  threshold (or the hysteresis band) would trade more frequent nudges for catching savings earlier
  — a product tradeoff (interruption cost vs. token savings) that should be made from a real
  distribution, not a guess. If sessions rarely approach it, the threshold is fine as-is and the
  strategy stays correctly rare.
- **Acceptance:** a decision, backed by the near-miss data, either to leave `MAX_SESSION_CHARS`
  unchanged (with the reasoning recorded) or to change it with a stated target firing rate.

## Strategy 5 — Re-examine the "decided against" query/result cache ruling

`BACKLOG.md`'s F4 neighbor rejected a query/result cache as saving "embedding compute, not
tokens." That reasoning is correct for caching *embeddings*, but conflates two different caches: a
same-session cache keyed on `(corpus content hash, query string)` for **identical repeated search
queries** would skip re-running the search tool call and its output round-trip entirely — that's a
context-token saving (the tool-output tokens of the second identical search), not a compute
saving, and the original ruling doesn't appear to have considered that distinction.

- **Action:** re-open as a narrowly-scoped question — not "build a query cache" but "would a
  same-session cache of identical repeated `search.py` invocations produce measurable events under
  the existing `savings.jsonl` schema (basis=`measured`, since both sides of the cut — the
  original result and the skipped rerun — are known)?" This is a small, testable claim, not a
  reopening of the full original proposal.
- **Acceptance:** a written ruling (adopt / still-reject-but-for-a-corrected-reason) recorded in
  `BACKLOG.md`'s "Decided against" section either way, so the distinction is preserved for future
  reviews instead of being re-litigated from scratch again.

## Sequencing

1. Strategy 1 (calibrate) — zero dependencies, do immediately.
2. Strategy 2 Phase A+B (fix contamination + isolation test) — blocks Phase C (mode flip) and
   blocks the liveness audit from being trustworthy (a dormant-v2-plane reading is meaningless
   while its log is 100% test noise).
3. Cross-cutting quantification framework (registry + audit command + the two CI gates) — needs
   Strategy 2's fix landed first so the v2 plane's liveness reading is real.
4. Strategy 3 and Strategy 4 Phase 0 (near-miss instrumentation) can start in parallel with #2/#3 —
   purely additive, no dependency on the budget-plane fix.
5. Strategy 3 Phase 1-2 and Strategy 4's threshold decision — gated on their own Phase 0 data
   existing, so these are the last steps, not first.
6. Strategy 5 — independent, can happen any time; recommend after #3 lands so the "does a search
   cache save real tokens" question can reuse the same near-miss instrumentation pattern.

## Confidence

High on all file:line root causes (`events.py`, `context_cache.py`, `compact_trigger.py`,
`search_config.py` — all directly read). High on the CI-gate designs (both modeled on existing,
already-working precedents in this repo — `test_hooks_state_dir.py`, `changelog_gate.py`). Medium
on Strategy 3's exact flag-normalization allowlist and Strategy 4's threshold target — both
depend on near-miss data not yet collected, by design; guessing those numbers now would repeat the
mistake this whole plan is trying to fix.
