# Continue: less_tokens

> **Next focus:** fix the nested-cwd hook bug (now confirmed universal — all 16 Codex hooks share
> the bug, not just one), triage the newly-solved savings.html cause, de-noise Strategy 4's
> near-miss data before touching its threshold, and run Strategy 1 (calibration).

## Current state
HEAD is `b7b6841`, working tree has uncommitted changes (see below) — nothing pushed/committed
this pass. Governance-run team review (`program`+`tect`+`backend`+`qa`, T2, commissioned via
`ever_better`) completed 2026-07-08: `eb_review_8jul26.md` (new) is the third team document in
this repo, following `eb_eval_4jul26.md`/`eb_plan_4jul26.md` (2026-07-04).

## What happened this session
- **Team review** (`eb_review_8jul26.md`) re-checked enforceability/reliability/measurability for
  Claude and Codex against live repo state, not just the 07-04 plan's assumptions. Corrected one
  stale premise (Strategy 5's ruling was already written 2026-07-07 in `DECISIONS.md` — done, no
  action needed). New findings: the nested-cwd hook bug is universal across all 16 wired Codex hook
  commands, not scoped to one hook (severity raised); the untriaged "savings.html shows nothing"
  BACKLOG item is root-caused to this repo's own stale local Codex install, most likely the same
  nested-cwd bug's visible symptom (Claude's copy has real, just-stale data — probably no
  Claude-side bug); Strategy 4's near-miss threshold data is ~25% contaminated by hardcoded
  test-fixture round numbers (`600000`/`650000` in 4 test files), invisible to the existing CI
  isolation gate, so its threshold call still isn't ready.
- **Ran the fix the review recommended**: this repo's own dogfooded `.codex/` install was stale —
  predated the commit that widened `context-cache` to cover Codex Bash calls, so zero real
  cached-bash/grep telemetry had ever fired on the Codex side here. Verified the installer itself
  was correct (self-target install is intentionally guarded — see `install.py`'s Scenario E test —
  so refreshed via a throwaway nested clone: `git clone --local . .lt-bootstrap-tmp`, ran
  `install.py --agent codex --update --skip-deps --no-build` from inside it targeting the repo
  root, then deleted the clone). Result: `.codex/hooks.json` now has all 16 hooks (was missing 2:
  `context-cache`'s Bash `PostToolUse`, and one `.*` `PostToolUse`); 5 stale `.codex/hooks/*.py`
  files refreshed (`context-cache.py`, `truncate-output.py`, `search-first.py`,
  `post-edit-diff.py`, `listing-guard.py`); `AGENTS.md`'s less_tokens block pruned to match the
  current instruction-pruning pattern; `.gitignore` gained generated-state exclusions;
  `.less_tokens/config/budget.json`'s `agent_overrides.codex` went from `{}` to populated defaults
  (was empty, so nothing custom was clobbered). **This does not fix the nested-cwd bug itself** —
  it only brings this repo's own install current; the underlying relative-path defect in
  `install.py`'s Codex command generation is still open and still Codex's fix to make.
- Uncommitted from before this session (not touched): `BACKLOG.md` already had a manual
  one-line note about the savings.html symptom, no status — the review's root-cause finding above
  should be folded into that row rather than left as a bare note.

## Open work
See [BACKLOG.md](BACKLOG.md) and `eb_review_8jul26.md`'s prioritized action list.
1. **Codex nested-cwd bug** (Bugs table) — now confirmed to disable all 16 hooks, not one; needs a
   Codex-context session. Likely fix: absolute-path `.codex/hooks.json` commands (Claude's
   `.claude/settings.json` stays relative — harness resets Bash cwd to repo root between calls,
   Codex has no such guarantee).
2. **Fold the savings.html root-cause into `BACKLOG.md`'s bare note** — turn "research into why...
   showing nothing" into a proper Bugs-table row pointing at the nested-cwd bug as likely cause,
   now that this session's Codex install refresh isolated it to a local-install-staleness /
   nested-cwd interaction rather than a code defect in the regeneration script itself.
3. **Strategy 1** — run `stats.py --calibrate` once `ANTHROPIC_API_KEY` is available.
4. **Strategy 3/4** — de-noise `near_misses.jsonl` first (the 07-04 tests hardcoding
   `600000`/`650000` pollute Strategy 4's threshold data by ~25%; the CI isolation gate doesn't
   catch this because it only watches `.less_tokens/state/events.jsonl`, not the near-miss log).
   Do not guess at threshold numbers until the contamination is fixed or filtered.
5. **G10 ID collision** and **missing acceptance criterion** on the search-cache item — still open,
   pure docs/BACKLOG edits, no data dependency.
6. **Commit this session's changes** — `.codex/` refresh is gitignored (no commit needed there),
   but `.gitignore`, `AGENTS.md`, `.less_tokens/config/budget.json`, `BACKLOG.md`, and the new
   `eb_review_8jul26.md` are real tracked changes still uncommitted.

## Suggested skills
- `/bugfix` for the nested-cwd bug (Codex-context session) or the near_misses.jsonl contamination.
- `/continue` — rewrite this once the nested-cwd bug lands, calibration runs, or near-miss
  contamination is resolved.

## Start here
If in a Codex-context session: fix the nested-cwd hook-command bug — it's now known to be
universal, not single-hook (`BACKLOG.md` Bugs table + `eb_review_8jul26.md` have the full case).
Otherwise: commit the pending tracked changes first (item 6 above), then either fold the
savings.html finding into `BACKLOG.md` (item 2, quick) or start de-noising `near_misses.jsonl`
before touching Strategy 3/4.

---
_Last updated at HEAD `b7b6841` (working tree dirty) on 2026-07-08._
