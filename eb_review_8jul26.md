# less_tokens Enforceability / Reliability / Measurability Review — 2026-07-08

Follow-up to `eb_eval_4jul26.md` (effectiveness eval) and `eb_plan_4jul26.md` (improvement plan +
quantification framework). Commissioned via `ever_better`
(`../ever_better/reports/runs/2026-07-08-less-tokens-enforceability-review/RUN_LOG.md`). Client
objective: make the token-reduction strategies more **enforceable**, **reliable**, and
**measurable**, for Claude and Codex specifically. Team: `tect` (architecture/enforcement-
mechanism soundness), `backend` (implementation root-causing), `qa` (measurability/test-gate
verification); `program` synthesizes. Method: verified current repo state against both prior
docs and the 07-04 commit (`f95a963`) rather than trusting the commissioning brief's summary —
one material correction and several new findings came directly out of that verification.

## Correction to the commissioning brief

**Strategy 5 already has a written ruling — it is not open.** The brief's context said no ruling
was recorded in `BACKLOG.md`'s "Decided against" section; that section moved to `DECISIONS.md` on
2026-07-04 (`e5c0656`) and the ruling *is* there, dated 2026-07-07: same-session `search.py`
repeated-query cache — real repeat rate ≈3-4%, stays periphery, **skip**, reopen only with fresh
evidence of a materially higher rate. `qa` re-verified the two evidence lines cited
(`near_misses.jsonl`'s 3 `"search"`-kind entries are pytest noise; `search-history.log`'s 83 real
queries / 3 same-session repeats) — both check out. **No further action on Strategy 5.**

## What's already strong — leave alone

- **Strategy 2 (v2 budget-plane fix + category_modes + liveness audit + label-consistency gate)**
  — `qa` re-ran both CI gates live: `label_consistency_gate.py` → `ok`, `test_hooks_state_dir.py`
  → 8/8 pass. `category_modes: {"unscored_context": "advise"}` is live in
  `.less_tokens/config/budget.json`; global `mode` is still `observe`, untouched. Working exactly
  as shipped.
- **The mtime/size context-cache bug fix** (`cad26af`) — confirmed still in place
  (`st_mtime`/`st_size` both checked in `check_read`).
- **Claude's hook-wrapper architecture is structurally drift-proof** (`tect`, new observation).
  `.claude/hooks/context-cache.py` and its siblings import shared logic live from
  `agents/common/hooks/*.py` at call time — there is no frozen copy to go stale. This is *why*
  Claude doesn't have — and structurally can't develop — the install-artifact-drift problem found
  below on the Codex side. Worth stating explicitly: it's the mechanical reason Claude enforcement
  can be flatly "enforced" while Codex's is "best-effort," beyond the documented harness/cwd
  reasons.
- **Truncation, search-first, and the compaction mechanism itself** — all fire correctly when
  their conditions are met; eval's ranking stands, nothing to re-litigate.
- **Strategy 3 & 4 Phase 0 instrumentation code** — `record_near_miss()` (bash/grep) and
  `record_session_size_sample()` (compaction) are both correctly implemented, additive-only,
  fail-open, matching the plan's design. The problem, where one exists, is downstream of the code
  (see below), not in it.

## New, highest-leverage finding: the Codex install in *this* repo is stale, not the allowlist

`eb_eval_4jul26.md` attributed zero cached-bash/cached-grep telemetry to `cacheable_bash_command()`
being too narrow. That's still true in principle, but `backend` traced a more immediate cause:

- `agents/common/hooks/hook_manifest.py`'s `context-cache` `HookSpec` was widened for Codex in
  commit `4b2efc6` ("Add Codex Bash context cache") to `PreToolUse mcp__filesystem__.*|Bash` +
  `PostToolUse Bash`.
- This repo's own locally-installed, gitignored `.codex/hooks.json` (confirmed gitignored:
  `.gitignore:29`) still only wires `context-cache` to `PreToolUse mcp__filesystem__.*` — it
  predates `4b2efc6` and nobody has re-run the installer against this dogfood copy since.
- `tect` verified the installer itself is **not** buggy: a from-scratch `install.py --agent codex`
  run into a scratch target directory correctly emits `PreToolUse mcp__filesystem__.*|Bash` +
  `PostToolUse Bash` for `context-cache`, matching the current manifest exactly.
- Consequence: on the Codex side, `check_bash`/`record_bash`/`record_near_miss(kind="bash")` have
  **never once executed** in this repo's real usage — `.less_tokens/state/near_misses.jsonl` has 0
  `"bash"`/`"grep"` entries against 6 `"session_size"` entries. This is a live-right-now
  enforceability and measurability gap, independent of the allowlist's width, and it is a
  one-command fix: **`python3 install.py --agent codex --update`** on the client's real
  `less_tokens` working copy. Not executed here (touches the client's live install state, judged
  out of this review's "no fixes unless truly trivial and clearly in-scope" boundary — a config
  re-sync of gitignored artifacts is low-risk but is the client's call to run).
- **Sequencing implication for `eb_plan_4jul26.md` Strategy 3:** run the install re-sync *before*
  Phase 1 (key normalization). Widening `cacheable_bash_command()`'s allowlist right now would
  still produce zero Codex telemetry — the trigger path is unwired locally, not narrowly gated.
  Claude was never in scope for the bash half of Strategy 3 to begin with: Claude's manifest
  entry has never included Bash (by design, not a bug) — `eb_plan_4jul26.md` didn't call out that
  Strategy 3's bash-cache work is Codex-only; worth stating explicitly so Phase 1/2 aren't scoped
  against Claude by mistake.

## New finding: the filed nested-cwd bug is universal, not scoped to one hook

`BACKLOG.md`'s open bug describes the nested-cwd relative-path failure as found on one hook
(`savings-html.py`, via the G15 test). `tect` checked all 16 wired entries in `.codex/hooks.json`:
**every single command uses the identical relative-path launcher pattern**
(`LESS_TOKENS_AGENT=codex .less_tokens/bin/python .codex/hooks/<name>.py`). There is nothing
hook-specific about the bug — from a nested cwd, *every* Codex hook (budget-observer, search-first,
read-guard, auto-slice, grep-first-read, read-after-edit, context-cache, post-edit-diff,
index-refresh, agentsmd-budget, lean-output, listing-guard, truncate-output, compact-trigger,
savings-html) fails silently (exit 127, no stderr). **This changes the risk rating materially**:
what was filed as a Codex-specific edge case in one acceptance test is, in practice, the single
largest enforceability risk in the whole Codex integration — a nested-cwd tool call disables
*all* less_tokens enforcement for Codex, unannounced, for that call. Recommend re-labeling its
priority from "left for a Codex-context session, whenever convenient" to the top Codex-specific
item, and pairing the fix with the already-flagged "Codex hook wrappers: collapse repeated adapter
boilerplate" backlog item (Architecture Simplification, High Priority) — that consolidation is the
natural single place to fix the relative-path launcher once for all 16 hooks instead of patching
`install.py`'s command-generation ad hoc. Assessment of that backlog item specifically: it is not
currently *blocking* (everything works from repo root), but it is the same root shape that made
this bug universal instead of contained to one wrapper, and will keep multiplying similar bugs as
hooks are added — upgrade its framing from "cleanliness" to "risk-reduction, pair with the
nested-cwd fix," not a full re-prioritization.

## Triage: "savings.html is showing nothing in codex or claude"

`qa` root-caused this rather than just reproducing it:

- **Codex (`.less_tokens/state/savings.html`)**: genuinely stale — `Generated: 2026-06-25 14:45`,
  all counts zero, despite `.less_tokens/state/savings.jsonl` gaining a real event on
  **2026-07-05 16:32:44** that never triggered a regeneration. Manually invoking
  `.codex/hooks/savings-html.py` from repo root regenerated it correctly on the first try (exit 0,
  fresh timestamp) — the script itself is not broken. Given every Codex hook shares the same
  relative-path launcher (previous finding), the most likely explanation is the already-filed
  nested-cwd bug silently killing the `PostToolUse .*` → `savings-html.py` invocation on whatever
  turns would have refreshed it. **High confidence this is the same bug's visible symptom, not an
  independent defect** — recommend closing this BACKLOG line as a duplicate pointer to the existing
  Bugs-table entry rather than a fresh investigation, contingent on hofmockel confirming the
  observation was made in a Codex context.
- **Claude (`.claude/state/savings.html`)**: not actually empty — it held real measured data as of
  its last generation (`Generated: 2026-07-05 13:24`, 306 all-time events, 646,104 tokens measured
  saved). It was simply stale because no Claude Code session had emitted a `Stop` event in this
  repo between 2026-07-05 and today. Manually invoking `.claude/hooks/savings-html.py` regenerated
  it correctly on the first try. **No evidence of a Claude-side defect** — the "or claude" half of
  the backlog line is most likely the client checking both without being sure which was actually
  broken. Recommend narrowing the BACKLOG item's wording to Codex-only once confirmed, rather than
  investigating Claude further.

## New finding: Strategy 4's near-miss data is ~25% contaminated, and the gap is invisible to CI

`.claude/state/near_misses.jsonl` (Strategy 4's compaction-threshold instrumentation, shipped
`f95a963`) has 120 `"session_size"` records collected 2026-07-04 → 2026-07-07. `backend` found 30
of them (25%) are the exact values `600000` (24×) and `650000` (6×) — literal byte counts hardcoded
in four separate unit test files (`test_bug_compact_trigger_stale_last.py`,
`test_hooks_state_dir.py`, `test_codex_hooks.py`, `test_hooks_protocol.py`). This is the same class
of test-suite-writes-into-production-telemetry bug that Strategy 2 fixed for
`.less_tokens/state/events.jsonl` — except `qa` confirmed the CI-blocking regression test added in
that same commit (`conftest.py::_no_production_telemetry_writes`) only watches
`.less_tokens/state/events.jsonl` (`_WATCHED_TELEMETRY_LOGS` is a single-item list); `near_misses.jsonl`
was never added to it on either side, so this contamination is currently invisible to CI. Unlike
the search near-miss log (which carries a `session_id` field you can filter pytest noise by),
`session_size` records carry no discriminator at all — `{"kind", "size", "threshold", "ts"}` only
— so filtering requires eyeballing for suspiciously-round numbers, which is fragile and won't scale.

- **Recommendation, before ruling on Strategy 4's threshold:** either tag `record_session_size_sample`
  calls with the same `session_id`/source marker `savings_log` events already carry, or extend the
  isolation test suite so the four offending tests redirect `LESS_TOKENS_STATE_DIR` the same way
  `test_hooks_state_dir.py`'s own compact-trigger cases already do (three of the four don't).
- **De-noised read of the real (84 unique, non-round) samples:** they range 1,000–539,244 chars
  over the 3-day window — approaching but not clearing the 500,000 threshold; the one all-time
  measured compaction (660,000 chars, predates this instrumentation) is not represented in this
  log. **Not enough clean data yet for a confident threshold call** — 3 days is thin, consistent
  with the plan's own "Medium confidence, depends on data not yet collected" caveat. Recommend
  clearing the contamination first, then let the window run longer before deciding.
- **New question the plan didn't ask:** the nudge (return-code-2 nag) fires whenever size clears
  threshold + hysteresis, which the *contaminated* portion of the log shows firing repeatedly
  (24+6 samples), yet the actually-measured compaction count is 1, all-time. Even discounting the
  contaminated rows, this raises a second question alongside "is the threshold right": **does the
  nudge reliably lead to an actual `/compact`, or is it frequently ignored?** That's a
  nudge-effectiveness question, not just a threshold-height one — worth folding into Strategy 4's
  scope rather than treating threshold height as the only variable.

## Prioritized next actions

1. **[Trivial, client-run]** `python3 install.py --agent codex --update` in the real `less_tokens`
   working copy — closes the install-drift gap, makes Strategy 3's Codex bash/grep near-miss data
   start actually collecting. Precondition for Strategy 3 Phase 1.
2. **Strategy 1 — calibrate the token estimate.** Still zero-dependency, zero-regression, still not
   run (`state/calibration.json` confirmed absent, both namespaces). Do this next; nothing above
   blocks it.
3. **Elevate and re-scope the nested-cwd bug.** Confirm it's universal (this review verified it is,
   across all 16 hooks); re-prioritize as the top Codex-specific fix rather than "whenever
   convenient"; scope the fix at the shared launcher-generation layer (pairs naturally with the
   Codex-wrapper-boilerplate consolidation already in `BACKLOG.md`), not per-hook patches.
4. **Close the savings.html BACKLOG line** as (very likely) a duplicate symptom of the nested-cwd
   bug for Codex, and not a Claude defect — pending hofmockel's confirmation of which agent context
   the observation came from.
5. **Fix `near_misses.jsonl` contamination visibility** (tag records or extend isolation-test state-dir
   overrides) before using Strategy 4's data to decide anything. This is a small, mechanical,
   two-way-door change — no near-miss data is lost, only future writes get cleanly separable from
   test noise.
6. **Strategy 3 Phase 1–2 (key normalization, TTL split)** — sequence after #1, once a real Codex
   data window exists. Still correctly gated on real data per the original plan; the blocker was
   never guessing the allowlist, it was the unwired install.
7. **Strategy 4's threshold decision** — not yet decidable at useful confidence; revisit after #5,
   with the reframed scope from the previous section (threshold height *and* nudge-to-compaction
   follow-through).
8. **Strategy 5** — closed, no action (see correction above).

## Enforceable / Reliable / Measurable — summary by axis and agent

| Axis | Claude | Codex |
|---|---|---|
| **Enforceable** | Strong — hooks import shared logic live, no drift surface; Strategy 2's category-mode gate live and tested. | Weaker than documented: "best-effort" is currently *worse* than its own design intends, for two compounding, fixable reasons — (a) this repo's own installed hook wiring has drifted from the manifest (fixable in one command), (b) the nested-cwd relative-path bug disables *all* 16 hooks silently, not just the one it was filed against. Neither is a ceiling on how strong Codex enforcement *could* be — both are currently-live, closeable gaps. |
| **Reliable** | No new reliability issues found; mtime/size fix holds. | The nested-cwd bug is a reliability issue with a real, observed symptom (stale savings.html) — raise its severity above "edge case." |
| **Measurable** | Near-miss telemetry for compaction is real but ~25% contaminated by test noise, invisible to the existing isolation gate — a measurement-integrity gap, not a Claude-vs-Codex one (the contamination is agent-neutral). | Near-zero measurable signal for cached-bash/grep specifically because the trigger path has never been wired locally — once #1 above is run, Codex's measurability for that strategy should match Claude's design intent (though Claude was never scoped to receive Bash events for context-cache in the first place). |

## Confidence

High on every claim backed by a direct code read, a live command run, or a file inspection in this
document (installer drift, universal nested-cwd pattern, near-miss contamination and its source,
gitignore status, CI gate results, Strategy 5's existing ruling) — all independently re-verified,
not taken from the commissioning brief. Medium on the savings.html-is-the-nested-cwd-bug's-symptom
claim specifically — plausible and consistent with all evidence gathered, but not reproduced
end-to-end through an actual Codex session with a nested cwd (would require a live Codex
environment this review didn't have). Medium on Strategy 4's threshold-vs-nudge-effectiveness
reframing — a real question raised by the data, not yet itself investigated. No claim above states
a token-savings magnitude without labeling it measured/upper-bound/asserted, per this repo's own
standing discipline.
