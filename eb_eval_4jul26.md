# less_tokens Effectiveness Evaluation — 2026-07-04

Team review commissioned via `ever_better` (governance framework tracking `less_tokens` as a
client project, see `../ever_better/reports/PORTFOLIO.md`). Scope: how effective is `less_tokens`
actually being for Claude and Codex, what should change, and does graphify help. Method: read
the shipped strategy table, the all-time savings telemetry (`.claude/state/savings.jsonl`, 264
real events), the budget-plane config and event log, and `BACKLOG.md`'s own prior self-assessment;
cross-checked by an independent `tect` pass (graphify fit) and `qa` pass (adversarial verification
of every claim below). Findings are labeled **measured** (real telemetry), **upper-bound**
(assumed avoided cost), or **asserted** (no telemetry exists) — same honesty discipline
`stats_plan.md` already established for this repo. Nothing below states a magnitude without
saying which of the three it is.

## Ordered by demonstrated effectiveness (most effective first)

1. **Tool-output truncation** — **measured**. 211 events, 1,600,278 chars / ~400k tokens saved,
   all-time (`stats.py --all`). By far the largest proven contributor: over 70% of every measured
   token saved in the repo's history comes from this one hook. Always-on, no model-behavior
   change requested, cheapest lever to keep exactly as-is.

2. **Search-first / grep-first / auto-slice (the input cluster)** — **upper-bound**. 22
   search-first blocks + 28 searches-vs-full-read, ≤1,242,928 chars / ≤310,732 tokens combined.
   This is the bucket `DOCUMENTATION.md:601-606` calls the single biggest lever (5–10×) and the
   volume backs that up, but every number here assumes "you'd otherwise have read the whole
   file" — never netted against the search actually run. Real, frequent, hook-enforced
   (PreToolUse blocks) — rank it just under truncation because it's the largest *assumed* number,
   not the largest *measured* one.

3. **Session compaction trigger** — **measured, but starved**. Exactly 1 event in all recorded
   history, and that single event saved 660,000 chars / ~165,000 tokens — the single largest
   number in the entire log. This is the highest per-event payoff strategy in the repo and it has
   fired once, ever. Worth investigating the trigger threshold: if it's gated on transcript size,
   the gate is plausibly too conservative given the payoff observed the one time it fired.

4. **Terse-output enforcement (caveman Stop hook)** — **asserted only**. README claims 30–60%
   fewer output tokens; the shipped `stats.py` categories (Truncation, Compaction, Cached
   read/grep/bash, Search-first, Search-vs-full) contain no row for this strategy at all — there
   is no telemetry mechanism for it and, by the nature of the strategy (no baseline "verbose
   version" to diff against), there may never be one. The hook is real and does fire every turn;
   the percentage in the README is not backed by any measurement in this repo.

5. **Instruction-file pruning (CLAUDE.md/AGENTS.md budget audits)** — **asserted only**, same gap
   as #4. `BACKLOG.md:20` itself already flags this as "the fixed bucket... barely touched beyond
   the just-shipped claudemd skill" — the repo's own prior self-assessment agrees this is
   under-built relative to its theoretical value (paid every turn, regardless of task).

6. **Cached read (repeat Read of same file)** — **measured, marginal**. 2 events, 7,579 chars /
   ~1,894 tokens, all-time. Mechanism works, real-world hit rate is negligible.

7. **Cached grep / cached bash** — **shipped, effectively non-functional**. Zero events, all of
   recorded history, for both. Independent verification confirmed the mechanism itself works when
   exercised directly (`context_cache.py` unit-level), but `cacheable_bash_command()` only
   qualifies exact-match `pwd`, `git status`, `rg ...`, or `pytest ...` within a short TTL — a gate
   narrow enough that real sessions never hit it. Not a bug; a design that is currently too
   conservative to ever pay off. As shipped, this row of the README's parity table (`README.md:56`)
   claims a capability that has never once saved a token in production.

8. **Budget control plane (v2)** — **shipped, currently inert for token reduction**. README calls
   this "always on... avoids irrelevant context before it is paid for," but
   `.less_tokens/config/budget.json:3` sets `"mode": "observe"` — the shipped default only
   *records* a decision, it never blocks, replaces, or defers anything. Worse: the plane's own
   event log (`.less_tokens/state/events.jsonl`, 160 events) is **100% pytest-artifact
   contamination** (`session_id: "contract-session"`, paths under `pytest-of-michael/...`) — a
   test-isolation leak, not real usage. This is this repo's most architecturally ambitious lever
   and it has never recorded a single real production decision, let alone enforced one.

9. **graphify integration** — **not adopted; reject as currently specified.** See below.

## What's not really working (bugs and gaps, independent of the ranking above)

- **v2 budget plane telemetry is 100% test noise** (`events.jsonl`) — fix the state-directory
  isolation leak before flipping `mode` away from `observe`, or the first real decisions will be
  buried in synthetic data from day one.
- **`cacheable_bash_command()` allowlist is too narrow to ever fire** — zero real hits confirms
  the gate, not the mechanism, is the problem.
- **Chars→tokens estimate has never been calibrated.** No `state/calibration.json` exists;
  `stats_plan.md:133` already documents a 10–30% error margin against Claude's real tokenizer.
  Every "tokens saved" figure anywhere in this repo — README, this document included — is an
  uncalibrated `chars÷4` estimate, not a measured token count.
- **`context-cache` trusts file mtime as proof of "unchanged"** — already flagged in
  `BACKLOG.md:63` with a real observed incident (2026-06-26, stale content silently served to an
  Edit). Correctness risk, not just a token-accounting risk.
- **Three README accuracy bugs already on record** (`BACKLOG.md:81-89`): `/def` lookup advertised
  as installed but not deployed by `install.py`; Codex hook wiring described as default-on when
  it's conditional on `.codex/` being writable; Codex install artifacts mischaracterized as
  adapter-hooks-only when `.claude/tools`/`.claude/schema`/`.claude/index.db` are shared. None of
  these affect real token savings, but they misstate what's actually shipped.
- **The G-series subagent strategies (`BACKLOG.md:26-39`, G7–G17) are entirely prose/discipline,
  not hook-enforced** — this repo's own backlog already says so ("no hook can force...",
  "discipline-only"). They're real ideas, correctly not counted as shipped wins, and correctly not
  claimed as measured savings anywhere.

## Could graphify help reduce tokens?

**No, not as currently specified — two unactioned `BACKLOG.md` items (lines 125, 127) already
flagged this as worth investigating; this closes that investigation.**

graphify's structural extraction (AST, free) is fine, but Part B — the semantic extraction that
builds the actual knowledge graph (entities, relationships, community detection) — dispatches
parallel Claude subagents that spend real input/output tokens, unless a Gemini/Google API key is
configured. Adopting graphify's default build path means **spending tokens to build the thing
that's supposed to save tokens** — a direct inversion of this repo's mission, and the same
reasoning this repo already used to reject a query/result cache tool ("saves embedding compute,
not tokens" — `DOCUMENTATION.md:625`). The capability gap is real: graphify's cross-entity
relationship queries and community/"god node" detection are things the flat vector+symbol index
genuinely doesn't do. But real capability ≠ token-reduction lever, which is this repo's specific
bar.

No artifact/state collision either way (`graphify-out/` is a distinct namespace from
`.claude/state/`, `.less_tokens/`, `.claude/index.db`) — the risk is entirely economic, not
technical.

**Conditional path, if ever revisited:** hard-gate the build to Gemini-backed extraction only
(never default to Claude subagents in this repo); scope it as an optional add-on for the *host*
repos `less_tokens` installs into, evaluated against their mission, not `less_tokens`'s own
dogfooding; and rewrite the two vague "investigate"/"install" backlog lines to state this
constraint explicitly so a future pass doesn't re-litigate the same default-cost problem.

## Deeper strategies to reduce token count (new, not already in BACKLOG.md)

1. **Calibrate the token estimate now.** `--calibrate` is already built, opt-in, network+key
   gated, and has simply never been run. Zero implementation cost, converts every "est." figure
   in every report (this one included) into a grounded number. Do this before anything else below.
2. **Fix `events.jsonl` test contamination**, then flip the v2 budget plane from `observe` to
   `advise` for the single lowest-risk category (`hard_caps.unscored_context`, already has
   `replacement_required_for_blocks: true`). Converts the repo's most ambitious, currently-inert
   lever into a real one, incrementally, starting where a wrong call costs the least.
3. **Instrument near-miss bash/grep repeats before widening the cache allowlist.** Rather than
   guessing which commands to add to `cacheable_bash_command()`, log commands that *would* have
   been cache hits if the gate were wider (repeated within TTL but not on the 4-pattern allowlist),
   then expand the allowlist from that real data instead of intuition.
4. **Investigate the compaction trigger threshold.** One event in all history produced the single
   largest saving on record (165k tokens). If the trigger is gated on a transcript-size threshold,
   check whether it's set high enough that it almost never fires in practice — this is the most
   under-triggered high-value lever in the repo.
5. **Re-examine the "decided against" query/result cache ruling** (`BACKLOG.md:43`, F4's neighbor
   in spirit). It was rejected because it "saves embedding compute, not tokens" — true for
   caching *embeddings*, but a same-session cache keyed on `(corpus content hash, query string)`
   for identical repeated *search queries* would return the same result chunks without re-running
   the search tool call and its output round-trip — that is a context-token saving, not a compute
   saving, and may have been dismissed under the wrong reasoning.

## Confidence

High on every **measured** figure (direct read of `.claude/state/savings.jsonl` and
`stats.py --all` output) and on the graphify build-cost mechanism (directly quoted from
`~/.claude/skills/graphify/SKILL.md`). Medium on "why cached grep/bash never fires in real
sessions" (gate logic confirmed narrow; not reproduced end-to-end through a live installed hook)
and on graphify's hypothetical payback conditions (no query-frequency telemetry exists for either
repo to test against).
