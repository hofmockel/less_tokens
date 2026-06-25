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

> **Reviewer (Codex): start with [Open questions for review](#open-questions-for-review).**
> Six decisions are unresolved; three block Phase 1. Everything else is a proposal
> we will change based on your answers.

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
- The dead `compaction` row, unless/until a real emitter ships (Open Questions).
- The `TRACK_SAVINGS` opt-in gate and every `if not TRACK_SAVINGS: return` branch.
  Tracking is unconditional (see Always on).

## Always on

Tracking runs from the first session of every install — no flag, no prompt.

- `savings_log.append()` drops the `TRACK_SAVINGS` guard. It stays failure-safe:
  wrapped in `try/except pass` so a logging error can never break a hook.
- It must stay **cheap** — one JSON line, one append, exact chars only, no tokenizer
  or network in the hot path. The hooks already compute the quantities; we only
  write them.
- The only escape hatch is removal, not a toggle: an undocumented
  `LESS_TOKENS_NO_STATS=1` env bail-out for users who must opt out, kept out of the
  normal config so it is not the default mental model.
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
  "session_id": "abc123"        // group events into the real session that produced them
}
```

Per strategy:

| Strategy | basis | `kept_chars` | `elided_chars` | Honesty |
|----------|-------|--------------|----------------|---------|
| Truncation (Bash/Glob) | `measured` | len(kept head+tail) | `original − kept` | exact both sides |
| Search-first block | `upper_bound` | 0 (you were redirected) | blocked file size | avoided cost assumed; the search you ran instead is unmeasured |
| Search vs full read | `upper_bound` | chunk chars returned (exact) | `sum(full file sizes) − chunk_chars` | kept side real; avoided side assumed |

This is the same data the hooks already have — `truncate-output.py`,
`search-first.py`, and `search.py` each already compute these quantities. The change
is the **schema** (`kept`/`elided`/`basis`/`session_id`), not new instrumentation.

`savings_log.append()` stays the thin writer it is. `session_id` comes from the hook
payload so the report can show *real sessions* instead of an 8h wall-clock guess.

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

- **Link**: the `Stop` hook emits a `file://…/state/savings.html` link (and the
  measured one-liner) in its output. Both Claude Code and Codex render that line in
  the transcript, so the user clicks through to the page. This is the
  lowest-assumption path and works identically in both.
- **Statusline (Claude Code)**: a statusline command prints
  `↓ ~122k tok saved (measured) · session` from the loader, measured-only to stay
  honest. Always visible, no click.
- **Codex**: surface the same one-liner through whatever turn-summary / notification
  channel the Codex integration already uses in this repo (the Codex-parity work);
  fall back to the transcript link if none. Confirm the exact channel during build —
  flagged in Open Questions so we don't assume a hook that isn't there.

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

1. **Always-on schema + loader** — drop `TRACK_SAVINGS`; new
   `kept/elided/basis/session_id` record; legacy-tolerant loader; update the three
   hooks to emit it. Unit tests for the arithmetic identities and the always-on
   write path.
2. **Report core** — measured vs upper-bound separation; real `session_id`
   grouping; honest token-estimate footer; Markdown `--report` for terminals/CI.
   Delete the fixture benchmark.
3. **HTML page** — `--html` self-contained renderer; `Stop`-hook regeneration so
   `state/savings.html` is always current.
4. **Surfacing** — `Stop`-hook link + measured one-liner in the transcript;
   Claude Code statusline; Codex turn-summary channel (confirm the channel first).
5. **Calibration (opt-in)** — `--calibrate` against `count_tokens` to ground the
   divisor in Claude's real tokenizer on our real content; HTML badge reflects state.

## Open questions for review

Each lists the decision needed and our current lean. **Blocks Phase 1** = must be
settled before we touch the schema/hooks; the rest can be decided as we reach them.

1. **`session_id` provenance — BLOCKS PHASE 1.** The new schema groups events by
   real session. Does the hook payload actually carry a stable session id in *both*
   Claude Code and Codex? If not, the whole "real sessions" framing degrades to the
   8h wall-clock guess we are trying to kill. Need confirmation of the field (and
   its name) in each harness before we commit the schema. *Lean: unknown — this is
   the first thing to verify.*

2. **Always-on privacy — BLOCKS PHASE 1.** Tracking becomes unconditional with only
   an undocumented `LESS_TOKENS_NO_STATS=1` bail-out. Acceptable for a tool that
   installs into other people's repos, or do we need a documented opt-out and a
   first-run notice? Log is local-only, never transmitted. *Lean: always-on, env
   bail-out only — but this is a product call, not ours to make alone.*

3. **Compaction strategy — BLOCKS PHASE 1 (scope).** Still has no emitter. Omit it
   from the schema/report until a real one exists, or build the emitter now and
   measure it like the rest? Affects whether Phase 1 includes new instrumentation.
   *Lean: omit until real.*

4. **Search-first kept side.** We log `kept_chars=0`, but the agent did run a real
   search with real cost. Capture that follow-up search's chars (linked via
   `session_id`) so the upper bound can later be netted toward a real figure — or
   leave it as a pure ceiling? *Lean: design the link now, net it down later.*

5. **Codex surfacing channel.** What does Codex expose for end-of-turn output in
   this repo's parity layer — a turn-summary hook, a notification, or only the
   transcript? Determines whether the one-liner has a home beyond the `file://`
   link. *Lean: transcript link as the floor; richer channel if one exists.*

6. **Calibration sample.** Which content mix best represents real token spend for
   `--calibrate` — this repo's own files, or captured live tool outputs? Wrong
   sample biases the divisor. *Lean: start with repo files; revisit if biased.*
