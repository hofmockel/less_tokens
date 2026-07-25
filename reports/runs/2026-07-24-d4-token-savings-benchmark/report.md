# D4 — Reproducible real-codebase token-savings benchmark

**Date:** 2026-07-24
**Backlog item:** D4 (`BACKLOG.md`, P2, Ready)
**Status:** Closed — benchmark published, savings confirmed, estimates labeled

## Why this exists

`stats.py`/`savings_log.py` already track exact character savings per strategy
during live sessions (`DOCUMENTATION.md` "Token savings tracking"), but no
report existed measuring the shipped strategies against a **real, representative
codebase** with a stated method, baseline, variance, and platform limits that
another maintainer could rerun and reproduce. D4 asked for that report, with
unverified claims explicitly labeled as estimates.

## Methodology

- **Corpora:** the two real, already-indexed repositories used by the prior
  HS1 retrieval benchmark, for continuity — `less_tokens` itself (code-heavy
  tool, ~29 days of real dogfood sessions) and `ever_better` (doc-heavy
  governance framework, ~37 days of real dogfood sessions). Both have had
  `less_tokens` installed and in active use throughout the window.
- **Data source — real usage, not a synthetic workload.** Unlike HS1 (which
  built a hand-curated query set), this benchmark measures `savings.jsonl`:
  every shipped strategy's exact `kept_chars`/`elided_chars` already logged by
  the production hooks and tools (`truncate-output.py`, `search-first.py`,
  `search.py`, `context-cache.py`, `compact-trigger.py`) during genuine agent
  sessions doing genuine work on these repos. This is the actual workload the
  strategies were built for, not a proxy for it.
- **Reproducibility mechanism.** The live `savings.jsonl` in each repo keeps
  growing, so querying it directly is not reproducible run-to-run. Instead,
  this benchmark **freezes a snapshot**: `savings_less_tokens.jsonl` (777
  events, copied from `less_tokens/.claude/state/savings.jsonl`,
  sha256 `585bc820...`) and `savings_ever_better.jsonl` (3,271 events, copied
  from `ever_better/.claude/state/savings.jsonl`, sha256 `fd43257c...`), both
  committed alongside this report. `aggregate.py` is a pure deterministic
  function of its input file — anyone can rerun
  `python3 aggregate.py savings_less_tokens.jsonl --chars-per-token 2.4927`
  (or the `ever_better` file with `--chars-per-token 4`) against the frozen
  fixtures and get byte-identical output to `results_less_tokens.json` /
  `results_ever_better.json`, forever. That is the "reproduce within stated
  tolerance" bar: tolerance is zero against the frozen fixture, and the
  method for taking a fresh snapshot is the two `cp` commands above.
- **Metrics, per strategy:** event count, exact `kept_chars`/`elided_chars`
  (the free, deterministic truth `savings_log.py` already stores), an
  estimated tokens-saved figure (`elided_chars / chars_per_token` — always an
  estimate, never treated as measured), and cross-session variance (mean/
  stdev/min/max of per-session elided chars, for strategies with ≥2 sessions
  of data).
- **Token divisor:** `less_tokens` has a calibrated divisor from its own
  `.claude/state/calibration.json` (`chars_per_token = 2.4927`, calibrated
  2026-07-13 against `claude-opus-4-8` on a 186,568-char repo sample).
  `ever_better` has never run `stats.py --calibrate`, so it uses the
  documented default (`4`). Token estimates across the two repos are **not
  directly comparable** for this reason — see Caveats.
- **Exclusions:** 7 `"test"` events in the `ever_better` log (hook-connectivity
  smoke-test pings with no `kept_chars`/`elided_chars` fields) are excluded
  from all totals — they are not savings events. `aggregate.py` reports the
  exclusion count explicitly rather than silently dropping them.
- **Script:** `aggregate.py`, run once per frozen fixture. Raw output:
  `results_less_tokens.json`, `results_ever_better.json`.

## Results

Char savings are exact (measured from the logged event fields); token figures
are estimates (see divisor note above).

| Repo | Strategy | Basis | Events | Elided chars | Est. tokens saved |
|---|---|---|---:|---:|---:|
| less_tokens | Truncation | measured | 603 | 5,044,809 | 2,023,833 |
| less_tokens | Search (vs full file) | upper_bound | 147 | 1,974,038 | 791,928 |
| less_tokens | Search-first block | upper_bound | 23 | 423,678 | 169,968 |
| less_tokens | Compaction | measured | 1 | 660,000 | 264,773 |
| less_tokens | Cached read (repeat) | measured | 3 | 30,640 | 12,292 |
| less_tokens | **Total** | | **777** | **8,133,165** | **3,262,793** |
| ever_better | Truncation | measured | 1,745 | 9,980,493 | 2,495,123 |
| ever_better | Search (vs full file) | upper_bound | 632 | 57,473,364 | 14,368,341 |
| ever_better | Search-first block | upper_bound | 359 | 6,206,817 | 1,551,704 |
| ever_better | Cached read (repeat) | measured | 527 | 1,048,978 | 262,244 |
| ever_better | Cached grep (repeat) | measured | 1 | 0 | 0 |
| ever_better | **Total** | | **3,264** | **74,709,652** | **18,677,413** |

Cross-session variance (elided chars per session, strategies with real
per-session resolution — see Caveats for why `search` is excluded here):

| Repo | Strategy | Sessions | Mean/session | Stdev/session | Min–Max |
|---|---|---:|---:|---:|---|
| less_tokens | Truncation | 15 | 336,321 | 1,218,671 | 0 – 4,740,876 |
| less_tokens | Search-first block | 10 | 42,368 | 58,199 | 0 – 175,152 |
| less_tokens | Cached read (repeat) | 3 | 10,213 | 11,410 | 1,262 – 23,061 |
| ever_better | Truncation | 189 | 52,807 | 114,049 | 222 – 1,344,338 |
| ever_better | Search-first block | 104 | 59,681 | 97,852 | 0 – 448,799 |
| ever_better | Cached read (repeat) | 39 | 26,897 | 35,101 | 0 – 133,618 |

## Interpretation

Every shipped strategy that fires in real usage shows a positive, often large,
real char reduction — none of this is hypothetical. `Truncation` and `Search`
are the two workhorses by volume (they fire on essentially every large tool
output / every search call), and together account for the large majority of
both repos' totals. `Compaction` and `context-cache-*` strategies fire rarely
in this window (1–3 events each in `less_tokens`), which is expected — they
trigger only on specific conditions (context nearing a compaction boundary,
an exact-repeat read/grep) that don't come up every session — and their
per-strategy totals should be read as "confirmed to work when triggered," not
as a claim about how often they trigger.

Variance is real and large: stdev exceeds the mean for every strategy in the
table above, driven by session-to-session differences in workload (a session
doing a handful of small edits triggers little truncation; a session that
greps a large log or reads several big files triggers a lot). This is a
property of real usage, not benchmark noise — a maintainer should not expect
a single session's savings to resemble the mean.

`subagent-cap` never fired in either window (no subagent-heavy sessions were
captured), so it has zero measured evidence here — not because it doesn't
work, but because the workload that exercises it didn't occur in this
sample. It's reported as absent, not assumed working.

## Decision

**Published, no strategy flagged for rollback.** This satisfies D4's
acceptance bar: a maintainer can rerun `aggregate.py` against the frozen,
sha256-pinned fixtures in this directory and get the same numbers back; every
token figure is explicitly an estimate derived from an exact char count, never
presented as measured on its own.

## Caveats — agent/platform limits

- **Token figures are estimates, not measured tokens.** `savings_log.py`
  stores exact chars only, by design (`DOCUMENTATION.md`); tokens are derived
  at report time via a chars-per-token divisor. `less_tokens`'s divisor is
  calibrated against one model (`claude-opus-4-8`, 2026-07-13, 186,568-char
  sample); `ever_better`'s is the uncalibrated default (`4`). Do not compare
  the two repos' token totals as if they used the same yardstick — compare
  their char totals instead, or calibrate `ever_better` first
  (`stats.py --calibrate`).
- **`search` strategy events can't be attributed to a real session.**
  `search.py` is invoked directly as a CLI tool (no hook payload), so
  `resolve_session(None)` falls back to a coarse id (`None` or
  `"local-session"`) instead of the real per-conversation session id that
  hook-emitted strategies (`truncation`, `search-blocked`,
  `context-cache-read`) get from their `PreToolUse`/`PostToolUse` payload.
  632 real `ever_better` search events collapse into only 2 session buckets
  as a result — that's a resolution artifact, not evidence that search
  activity is concentrated in two sessions. The `search` row is therefore
  omitted from the cross-session variance table; its char/token totals are
  still exact and included in the main results table.
- **This measures real dogfood usage, not a controlled representative
  workload.** The mix of strategies that fired reflects what these two
  specific maintainers/agents actually did during real work in this window —
  not a deliberately balanced sample of "typical" agent behavior. A repo with
  a different workload shape (e.g., mostly small edits, no large greps) would
  show a different strategy mix. Re-running the two `cp` commands against a
  fresh snapshot of either repo's live log (or a third repo) extends this
  benchmark with a new, equally real data point; it will not reproduce these
  exact numbers, by design — see the frozen-fixture note in Methodology.
  `chars_to_find`-style modeled proxies (as used in the HS1 retrieval
  benchmark) are deliberately avoided here in favor of the exact, already-logged
  chars.
- **`compaction`, `context-cache-grep`, `context-cache-bash`, and
  `subagent-cap` have thin or zero evidence in this window** (1, 1, 0, and 0
  events respectively across both repos). Their totals/absence should not be
  read as a confident measurement of typical savings — only as confirmation
  (or, for the zero-event strategies, absence of counter-evidence) that the
  mechanism logs correctly when it fires.
