# EB repo telemetry — external evidence for stalled backlog items

Source: `ever_better` (github.com/hofmockel/ever_better), a separate repo that installed this
tool and has been dogfooding it since ~2026-06-24. Not this repo's own production telemetry —
brought over by hand to supply real-world signal where this repo's own sample is currently too
thin. Do not merge into this repo's `state/*.jsonl` — those files are protected by
`conftest.py::_no_production_telemetry_writes` and must only ever contain events this repo's
own hooks generated.

## 1. Compaction threshold (`near_misses.jsonl`, kind=`session_size`)

BACKLOG.md's "de-noise near-miss telemetry before deciding the compaction threshold" item says
this repo's own de-noised sample is 84 clean points (of 120), ranging 1,000–539,244 chars —
"not enough signal yet either way."

EB's `.claude/state/near_misses.jsonl` (separate agent-state dir, not `.less_tokens/state/`)
has **3,024** `session_size` records, all real (checked: zero exact-multiples-of-10,000 —
this repo's known test-fixture pattern of `600000`×24 / `650000`×6 is absent here):

| Stat | Value |
|---|---|
| n | 3,024 |
| min | 43,374 chars |
| p50 | 411,074 chars |
| p90 | 890,614 chars |
| p99 | 1,270,514 chars |
| max | 1,414,558 chars |
| threshold configured (EB) | 625,000 chars (not this repo's 500,000 — different config, see caveat) |
| count > 500,000 (this repo's threshold) | 1,077 (35.6%) |
| count > 625,000 (EB's own threshold) | 758 (25.1%) |

Caveat: EB runs `MAX_SESSION_CHARS=625,000`, not this repo's 500,000, so the raw counts aren't
a direct test of *this* repo's configured value — but the underlying distribution (real Claude
sessions, same tool, same estimator) is the thing that was missing. At this repo's 500,000
threshold, over a third of EB's real sessions would have crossed it; the nudge is firing on a
non-trivial chunk of ordinary sessions, not just outliers. Doesn't replace the still-open code
fix (tagging `record_session_size_sample` calls / isolating the 4 offending tests from
`_no_production_telemetry_writes`) — that contamination is in *this* repo's fixtures, and EB's
clean data doesn't touch it. It does mean the threshold-height call no longer has to wait on
this repo's own sample to grow.

Second question in that same item — does the return-code-2 nudge actually lead to `/compact`,
or get ignored: this repo's own count was 1 all-time. EB's budget-plane telemetry (separate,
newer pipeline, see §3) recorded **3,364** compaction events against 24,852 total decisions —
a much higher real hit rate, though it's a different mechanism (budget-pressure compaction, not
the char-threshold nudge this item is about) so treat as directional, not a direct answer.

## 2. Cache-key widening for bash/grep (`near_misses.jsonl`, kind=`grep`)

BACKLOG.md's "widen cache keys" item is blocked on real Codex-side near-miss data specifically
(the repo's local Codex install had drifted stale until 2026-07-08). EB only runs the Claude
agent, so this doesn't fill that specific gap — flagging so it isn't mistaken for Codex
evidence. What it does supply is a small, real example set of the failure pattern the item
is trying to fix (semantically-identical patterns that miss cache because they're not
byte-identical), useful as raw material when designing the normalization allowlist:

```
round 25|round-25
gen_agent_runtimes|round 25|link
\]\(                                              (recurs 3x)
^## Precedence|^## Claim labels|^## Confidence scale|^## Output template
ENFORCEMENT_MAP
DECISION_WORKFLOW|P0-1|P0-2|P0-4
^## (Precedence|Claim labels|Confidence scale|Output template)   <- same set as above, reformatted
PostToolUse|Edit\|Write|matcher
Shared library API contract
def source_names|external|LINK_RE|rewrite_relative_links|ANCHOR_HEADERS
## Shared library API contract                                   <- same as above, reformatted
```
n=13. Two pairs above are the same logical query re-expressed (alternation reordered into a
group, and a heading re-quoted with `##`) — exactly the "semantically-identical repeats" case
named in the backlog item.

## 3. Token-count calibration

BACKLOG.md's "calibrate the token-count estimate" item is blocked strictly on running
`stats.py --calibrate` with `ANTHROPIC_API_KEY` set — it isn't a data-volume problem. EB has
**not** run calibration either (no `calibration.json` in either agent's state dir); its figures
below are the same uncalibrated `chars÷4` estimate this repo's own are. EB's telemetry doesn't
unblock this item — noting so it isn't assumed to.

## 4. Volume, for context (not a backlog blocker, just scale)

Legacy strategy log (`.claude/state/savings.jsonl`, 1,425 events — the same schema `stats.py`
reads, vs. this repo's own all-time count of 1):

| Strategy | Events | Chars saved |
|---|---|---|
| search | 455 | 48,033,417 |
| context-cache-read | 439 | 4,271,396 |
| search-blocked | 205 | 2,105,311 |
| truncation | 327 | 970,157 |

Newer budget/relevance-gate pipeline (`.less_tokens/state/events.jsonl`, all-time, 24,852
decisions): **9,944,538** estimated tokens saved, 3,364 compactions, dominated by
`relevance_gate` defer/block/trim. Same uncalibrated estimator as everything else in this file.

## Bottom line

- Compaction-threshold item: real signal now exists (§1) — enough to make the height call
  without waiting on this repo's own sample; the test-isolation bug is still this repo's own
  fix to make.
- Cache-key-widening item: still blocked on real Codex data specifically; §2 is example
  material only, not the unblock.
- Calibration item: unaffected by any of this — needs the `--calibrate` run.
