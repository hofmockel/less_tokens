# Stats Framework Rewrite — Measure Production Reality

This plan **replaces** the current stats framework. No synthetic fixtures, no
benchmark theater, no fabricated "we saved X%" assertions. We measure what actually
happens in real sessions, at the moment each strategy fires, and we show the user
those real numbers — clearly labelled by how trustworthy they are.

Two product decisions frame the rest:

- **Always on.** Tracking is no longer opt-in. Every install logs from the first
  session; there is no flag to forget to flip.
- **The deliverable is an HTML status page**, regenerated from the real log and
  surfaced inside both the Claude and Codex interfaces.

> **Review status:** open questions resolved below. Phase 1 can start once the
> session-id fallback and privacy notice are reflected in code/docs.

## Principle

A saving is only real if it is **what actually happened**, not what we assume would
have happened. Two kinds of event exist and we never blur them:

- **Measured** — we hold both sides of the cut, so the saving is exact arithmetic.
  Truncation is the only true case: the hook sees the full tool output and the
  kept head+tail, so `elided = original − kept` is a fact.
- **Upper bound** — we redirected the agent and are *guessing* the avoided cost.
  Search-first and search are these: we assume "you'd otherwise have read the whole
  file(s)." The kept side is real; the avoided side is an assumption.

The report shows these in **separate sections** and never sums them into one
headline number. That single rule is what makes the report honest.

## What we delete

- `tests/perf/test_bench_tokens.py` and any fixture-driven "reduction ratio"
  benchmark. Those numbers are properties of hand-built fixtures, not of real use.
- The chars÷4 token figure presented as if it were a count. Tokens become an
  explicitly labelled estimate everywhere (see Token honesty).
- The dead `compaction` savings row as a placeholder. If compaction appears in the
  savings report, this rewrite must add a real compaction savings emitter that logs
  the same `kept_chars`/`elided_chars` schema as every other strategy.
- The `TRACK_SAVINGS` opt-in gate and every `if not TRACK_SAVINGS: return` branch.
  Tracking is unconditional (see Always on).

## Always on

Tracking runs from the first session of every install — no flag, no prompt.

- `savings_log.append()` drops the `TRACK_SAVINGS` guard. It stays failure-safe:
  wrapped in `try/except pass` so a logging error can never break a hook.
- It must stay **cheap** — one JSON line, one append, exact chars only, no tokenizer
  or network in the hot path. The hooks already compute the quantities; we only
  write them.
- The escape hatch is documented but not prompted: `LESS_TOKENS_NO_STATS=1`
  disables local savings logging for users who need it. It stays outside
  `search_config.py` so the default mental model remains "local telemetry is on."
- The installer and docs must say plainly that savings telemetry is local-only,
  what it records, and how to disable it. No interactive first-run prompt.
- The log is **local only** (`state/savings.jsonl`), never transmitted. "Always on"
  means always *recorded*, not always *sent* — the calibration API call stays the
  one opt-in network action.

## Event schema (`state/savings.jsonl`)

One JSON line per event. Events store **exact characters** — the free, deterministic
truth — and enough context to render and audit. They do **not** store tokens; tokens
are derived at report time so we can re-estimate the whole history when the ratio
improves.

```json
{
  "ts": 1750000000.0,
  "strategy": "truncation",
  "basis": "measured",          // "measured" | "upper_bound"
  "kept_chars": 3987,           // what actually entered context (exact)
  "elided_chars": 37835,        // what did not (measured fact, or assumed bound)
  "content_kind": "tool_output",// tool_output | source_file | search_result
  "where": "Bash",              // tool name / file path / query — for audit
  "session_id": "abc123",       // group events into the real session that produced them
  "session_source": "payload",  // payload | transcript_path | env | local
  "correlation_id": "sf:..."    // optional: link redirects to later search events
}
```

Per strategy:

| Strategy | basis | `kept_chars` | `elided_chars` | Honesty |
|----------|-------|--------------|----------------|---------|
| Truncation (Bash/Glob) | `measured` | len(kept head+tail) | `original − kept` | exact both sides |
| Compaction | `measured` | compacted summary chars | `pre_compaction_transcript_chars − compacted_summary_chars` | exact only when the emitter sees both texts |
| Search-first block | `upper_bound` | 0 (you were redirected) | blocked file size | avoided cost assumed; the search you ran instead is unmeasured |
| Search vs full read | `upper_bound` | chunk chars returned (exact) | `sum(full file sizes) − chunk_chars` | kept side real; avoided side assumed |

This is the same data the hooks already have — `truncate-output.py`,
`search-first.py`, and `search.py` each already compute these quantities. Compaction
is the exception: including it requires new instrumentation that records the
pre-compaction transcript size and the produced compact summary size at the moment
the compaction snapshot is generated. The shared rule still holds: no event is
reported unless the emitter has both sides of the cut.

`savings_log.append()` stays the thin writer it is. `session_id` is resolved in one
shared helper, in this order:

1. Native payload field: `session_id` if present.
2. Stable transcript identity: hash of `transcript_path` if present.
3. Environment: `LESS_TOKENS_SESSION_ID`.
4. Last-resort local bucket: `local-session`.

The existing code already normalizes `transcript_path` for both Claude and Codex
payloads, and the budget adapter already accepts `session_id` when the harness
provides one. That means Phase 1 is not blocked on proving a new native Codex field:
the schema stores a stable `session_id` plus `session_source`, and reports label
`local-session` as "session unavailable" instead of pretending it is a real
session. Do not return to the old 8h wall-clock grouping except as a legacy view for
old records.

### Migrating old logs

Old records lack `basis`/`kept_chars`/`session_id`. The loader treats any record
without `basis` as legacy: it maps the old `saved_chars` to `elided_chars`, infers
`basis` from `strategy` (truncation→measured, else upper_bound), and tags
`content_kind="legacy"`. No rewrite of the file; the reader is tolerant.

## Token honesty

We save **Claude** tokens, and there is no offline Claude tokenizer. So:

- **Chars are the stored truth.** Exact, free, deterministic.
- **Tokens are always an estimate**, computed at report time as
  `chars / CHARS_PER_TOKEN`, and **always rendered with the word "est."** and the
  divisor in the footer. Never presented as a measured count.
- We **do not** ship tiktoken and pretend it is Claude — OpenAI's tokenizer drifts
  10–30% from Claude on code and non-English, so calibrating our shipped divisor to
  it would make the estimate *worse* for the model we actually care about.
- **Optional, opt-in `--calibrate`**: samples representative real content (this
  repo's own code, prose, and a few captured tool outputs), sends it to Anthropic's
  `count_tokens` endpoint, and computes the true chars-per-token for *our* content
  against *Claude*. Writes the result to `search_config.CHARS_PER_TOKEN` with a
  dated comment. This is the only path that grounds the estimate in the real model;
  it is network + key gated and never runs automatically. Until run, the footer
  reads `tokens est. at chars÷4 (uncalibrated)`.

## The HTML status page

The deliverable users see is `state/savings.html` — a single self-contained file
(inline CSS/JS, no network, no build step) generated from `savings.jsonl`. Same
honesty rules as everything else: measured and upper-bound kept visually separate,
tokens labelled "est.".

Layout:

- **Header**: total measured tokens saved (est.), this session and all-time, with
  the calibration state badge (`chars÷4 uncalibrated` vs `calibrated <date>`).
- **Measured panel** — "actually removed before reaching the model": per-strategy
  table + a bar of chars removed over recent sessions.
- **Upper-bound panel** — visually subdued (muted color, "≤" prefix, a one-line
  disclaimer) so it never reads as money in the bank.
- **Recent events** table for audit: ts, strategy, basis, kept/elided chars, where.

Generation:

- A renderer in `stats.py` (`--html` writes the file; the existing `--report` still
  writes the Markdown variant for terminals/CI).
- Regenerated by the **`Stop` hook** at the end of each turn, so the page is current
  whenever the user opens it. Cheap: read log, render template, write file.
- Pure stdlib templating (an f-string/`string.Template`), no JS framework, so it
  works in the locked-down install with zero deps.

## Surfacing in the Claude / Codex interface

Neither interface renders HTML inline, so the integration point is a **clickable
link to the generated file**, plus a glanceable one-liner. Both read the same log;
nothing interface-specific lives in the data layer.

- **Claude link**: the `Stop` hook emits a `file://…/state/savings.html` link (and
  the measured one-liner) in its output, so the user can click through from the
  transcript.
- **Statusline (Claude Code)**: a statusline command prints
  `↓ ~122k tok saved (measured) · session` from the loader, measured-only to stay
  honest. Always visible, no click.
- **Codex**: generate the same `state/savings.html` file and expose its path through
  the safest available channel. Current parity wiring exposes Codex PostToolUse
  adapters, not a native Stop hook, so Phase 4 must not depend on end-of-turn
  Codex output. A richer Codex one-liner is allowed only after implementation
  confirms a durable channel.

We do **not** claim native in-TUI HTML rendering. The HTML is a browser artifact;
the interfaces surface a link and a number.

## Tests — plumbing only, zero fabricated savings

We test that the **measurement code is correct**, never that a made-up input
"saves" a made-up amount. Concretely:

- `elided_chars == len(original) − len(kept)` given real strings — an arithmetic
  identity, deterministic, no fixtures.
- `basis` classification per strategy is correct.
- The loader maps legacy records and tolerates malformed lines (already covered).
- The report renders measured and upper-bound into separate sections and never
  cross-sums them.

No test asserts a savings *magnitude*, because magnitude is a property of real
sessions, not of code. That is the whole point: numbers come from production, tests
only guard the pipe.

## Phases

0. **Teardown — remove fixture benchmark** — delete `tests/perf/test_bench_tokens.py`
   and any fixture-driven "reduction ratio" assertion. Pure removal, no replacement
   dependency: it tests fabricated numbers this rewrite rejects outright, and leaving
   it in keeps CI green on a contract the rewrite deletes. Done first so it stops
   gating the rewrite. (Other deletions — `TRACK_SAVINGS`, the compaction placeholder
   row — are coupled to their replacements and stay in Phases 1–2, not here.)
1. **Always-on schema + loader** — drop `TRACK_SAVINGS`; add
   `kept/elided/basis/session_id/session_source` records plus optional
   `correlation_id`; legacy-tolerant loader; update the three existing hooks to
   emit it.
   Unit tests for the arithmetic identities, session-id fallback order, documented
   env opt-out, and always-on write path.
2. **Compaction emitter** — add a savings emitter to the compaction path that logs
   `basis="measured"`, `kept_chars=len(compacted_summary)`, and
   `elided_chars=max(0, pre_compaction_transcript_chars - kept_chars)`. It should
   fire only when both sides are available; otherwise it logs no savings event.
3. **Report core** — measured vs upper-bound separation; real `session_id`
   grouping; honest token-estimate footer; Markdown `--report` for terminals/CI.
4. **HTML page** — `--html` self-contained renderer; `Stop`-hook regeneration so
   `state/savings.html` is always current.
5. **Surfacing** — `Stop`-hook link + measured one-liner in the Claude transcript;
   Claude Code statusline; Codex transcript/file link as the floor, with a richer
   Codex turn-summary channel only if one is confirmed during implementation.
6. **Calibration (opt-in)** — `--calibrate` against `count_tokens` to ground the
   divisor in Claude's real tokenizer on our real content; HTML badge reflects state.

## Review decisions

1. **`session_id` provenance — resolved.** Do not block Phase 1 on a native field
   existing in both harnesses. Use a shared resolver: payload `session_id`, then a
   stable hash of `transcript_path`, then `LESS_TOKENS_SESSION_ID`, then
   `local-session`. Store `session_source` so reports can distinguish real sessions
   from fallback buckets. The budget adapter already has payload/env support, and
   the shared hook payload already carries `transcript_path`; align savings logging
   with that pattern.

2. **Always-on privacy — resolved.** Tracking can be always-on because it is local
   only, but the opt-out must be documented. Add installer/docs copy that says the
   log records local event metadata and character counts, never uploads them, and
   can be disabled with `LESS_TOKENS_NO_STATS=1`. Do not add a config toggle or
   prompt.

3. **Compaction strategy — resolved.** Add a real compaction savings emitter if
   compaction is included in the savings report. Do not reuse the existing v2 budget
   compaction telemetry as savings by itself: it is token-estimate telemetry, not a
   measured `kept_chars`/`elided_chars` event. The new emitter must only log when it
   can see both the pre-compaction transcript text/size and the compacted summary
   text/size.

4. **Search-first kept side — resolved.** Keep `kept_chars=0` for the redirect
   event in Phase 1 and add an optional `correlation_id`. Search events can later
   carry the same id or a `caused_by` field so the report can net the follow-up
   search cost without changing the base schema.

5. **Codex surfacing channel — resolved.** Treat the transcript/file link as the
   only guaranteed Codex surface. The current manifest has Codex PostToolUse
   adapters but no native Stop hook equivalent, so richer end-of-turn surfacing must
   be opportunistic and separately confirmed.

6. **Calibration sample — resolved.** Start with repository files plus a bounded
   sample of recent captured tool outputs when available. Label the resulting
   divisor with sample counts and date. If no tool-output samples exist, calibrate
   from repo files only and mark the badge `repo-sample calibrated` rather than
   implying it represents all runtime output.
