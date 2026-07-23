# CP1 — Does snapshot-guided compaction improve task-critical-fact recall over a generic nudge?

**Date:** 2026-07-22
**Backlog item:** CP1 (`BACKLOG.md`, P1, Research)
**Status:** Closed — no measured recall gap at feasible spike scale; do not wire (tracked as Rejected decision)

## Why this exists

`compact_trigger.py`'s Claude-side hook (`.claude/hooks/compact-trigger.py`) emits a generic
nudge when the transcript exceeds threshold: *"Run /compact or start a fresh Claude session
before more work."* Separately, the budget control plane (`agents/common/budget/compaction.py`)
already tracks `active_files`, `decisions_made`, `test_status`, `open_questions`, `next_step`,
and `current_objective` per session and can render them into a token-budgeted
`compact_summary` via `build_compaction_snapshot()`. The two paths are not connected — the
snapshot is computed (and, on Codex, written to state at `PreCompact` per CX20/CX29) but never
fed into the message that actually reaches the model at the moment it decides to run `/compact`.

CP1 asked: if the nudge instructed `/compact <preserve-these-facts>` instead of a bare
`/compact`, would the resulting summary retain more task-critical facts? Only wire the change if
recall measurably improves.

## Methodology

Recall of an actual live `/compact` run can't be scripted deterministically — it depends on
model judgment, not code under test. The chosen proxy: have a fresh LLM instance (a
`general-purpose` subagent, same model class Claude Code itself runs) perform an
analogous compaction task twice on identical input — once under a generic instruction (mirrors
today's hook message), once under an instruction that explicitly lists the facts a
`compact_summary`-derived snapshot would carry — and score recall of a fixed fact checklist
against each output. This tests the actual causal mechanism (does explicit preservation
instruction increase fact retention in an LLM-produced summary), using the same class of model
that performs real Claude Code compaction.

- **Fixture:** `synthetic_transcript.md` — a fabricated but realistic Claude-Code-style session
  transcript (tool calls, back-and-forth, dead ends, decisions, test runs). Round 1 is a single
  ~150-line coherent thread (a Stripe refund webhook race-condition fix). Round 2 appends a
  second, unrelated ~150-line thread (a support-search field-mismatch bug) *after* the refund
  thread, specifically to introduce recency bias — a generic summarizer asked to compact a
  session that ends on topic B is a plausible way to lose topic A's least-recent facts, which
  is exactly the failure mode explicit preservation instructions are supposed to prevent.
- **Snapshot generation:** the guided condition's fact list was produced by actually calling
  `build_compaction_snapshot()` (`agents/common/budget/compaction.py`) against a hand-populated
  state dict matching the transcript's content, confirming it fits the real `session_summary`
  budget (`estimated_tokens: 387` against `budget_limit: 3000`, no trimming needed) — not just
  hand-authored guidance disconnected from the real code path.
- **Conditions**, run as two independent `general-purpose` subagents per round (fresh context,
  no knowledge of the other condition):
  - **Generic** — told the transcript needs compacting for a fresh session to continue,
    mirroring the current hook's bare nudge.
  - **Guided** — told the same, plus given the `compact_summary`-derived fact list and instructed
    to preserve those facts verbatim/near-verbatim while compacting everything else normally.
- **Scoring:** an 8-item critical-fact checklist fixed before reading any output — TOCTOU root
  cause, the Redis/24h-TTL decision, the $5,000 ceiling decision, the failing rounding test
  (12.34 vs 12.33), the Decimal next-step, the merchant_id/charge_id open question, the
  dashboard-slowness secondary observation, and the session objective. Each output scored
  present/absent per item.
- **n=1 per condition per round** (2 rounds × 2 conditions = 4 subagent runs total). This is a
  bounded spike, not a statistically powered study — see Limitations.

Raw outputs: `round1_generic.md`, `round1_guided.md`, `round2_generic.md`, `round2_guided.md`.

## Results

| Round | Condition | Recall (8-item checklist) |
|---|---|---|
| 1 (single thread) | Generic | 8/8 |
| 1 (single thread) | Guided | 8/8 |
| 2 (two threads, refund thread not most-recent) | Generic | 8/8 |
| 2 (two threads, refund thread not most-recent) | Guided | 8/8 |

No recall gap in either round, including round 2's deliberate recency-bias stress case — the
generic condition's summary still surfaced the refund thread's `next_step` as an explicit
"immediate next action... not yet done" even though the transcript ended on the unrelated search
thread.

## Interpretation

At the scale this spike could feasibly fabricate (roughly 150-300 lines of transcript, well
short of the ~625,000-750,000 char real trigger threshold `compact_trigger.py`/
`search_config.MAX_SESSION_CHARS` actually fires at — see the live 636,593-char firing observed
in this very session while writing this report), a modern strong-model compaction pass already
recovers essentially all task-critical facts from a moderately-noisy, multi-thread transcript
without needing an engineered preservation prompt. The hypothesized failure mode (generic
compaction silently drops the least-recent thread's state) did not reproduce even when
deliberately induced.

This does not prove the mechanism is worthless at real compaction scale — a transcript two to
three orders of magnitude larger, with many more competing threads and far more discardable
noise, is a genuinely different compression regime, and generic instructions could plausibly
degrade there in a way this fixture is too small to expose. But producing and scoring a
realistic ~700K-char fixture (or capturing one from `near_misses.jsonl`/a live long session) with
enough trials to be more than anecdotal is a materially larger effort than a bounded spike, and
CP1's own acceptance criteria gate the wiring change on *measured* recall improvement — which
this spike did not find.

## Verdict

Per CP1's acceptance criteria ("wire the improved Claude nudge only if recall improves"): **do
not wire.** Leave `.claude/hooks/compact-trigger.py`'s generic nudge message as-is. Codex side
needs no action — CX20 already established hooks are advisory-only there, matching CP1's own
scoping ("keep Codex advisory-only unless CX20 establishes an invocation surface").

## Limitations / what would reopen this

- n=1 per condition per round is not statistically powered; a single lucky/unlucky subagent run
  could flip a result. Treat 8/8-vs-8/8 as "no gap detected at this fixture size," not
  "proven equivalent."
- Fixture size (~300 lines at round 2) is roughly three orders of magnitude below the real
  trigger threshold. Reopen with a realistic-scale fixture (captured from an actual long session
  near `MAX_SESSION_CHARS`, or fabricated at that scale) and enough trials for the comparison to
  be more than anecdotal.
- This proxy tests an LLM performing a compaction-shaped summarization task, not Claude Code's
  actual `/compact` implementation, which may have its own additional scaffolding/instructions
  this proxy doesn't reproduce.
