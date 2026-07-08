# Continue: less_tokens

> **Next focus:** everything actionable right now is instrument-first and blocked on real usage
> data. `BACKLOG.md`'s "Same-session `search.py` repeated-query cache" and the Strategy 3/4
> near-miss items (cached-bash, cached-grep, compaction threshold) all wait for `near_misses.jsonl`
> to accumulate from normal use before any further code change — do not guess at the numbers.
> `stats.py --calibrate` (Strategy 1) still just needs a session with `ANTHROPIC_API_KEY` present.

## Current state
HEAD is `f9214c8`, repo clean — everything below is committed, nothing pushed status checked.

Since the last handoff (`45e2e27`, 2026-07-04), in order:
1. **`f95a963`** — Strategy 2 fixes from `eb_plan_4jul26.md` (v2 budget-plane telemetry isolation,
   per-category budget modes), `stats.py --audit-liveness`, `label_consistency_gate.py`. This was
   the "uncommitted changes" the prior continue.md described as in-progress; it's committed now.
2. **`cad26af`** — fixed the context-cache mtime bug found by `ever_better`'s cross-repo
   `2026-07-04-less-tokens-backlog-review` (`tect`+`qa`): `check_read`/`record_read` now require
   `st_size` to match alongside `st_mtime`, closing the "unchanged" false-positive from
   `cp -p`/`rsync --times`/coarse fs granularity. Filed to `BACKLOG.md`'s Bugs table and cleared
   same commit, per protocol.
3. **`2f38b8b`** — near-miss instrumentation for `search.py`'s repeated-query path
   (`_record_search_near_miss()`, `state/search-session-cache.json`), same fail-open/additive
   discipline as the existing cached-bash/-grep instrumentation. Still does not build the cache
   itself — waits for data.
4. **`c11446e` → `f9214c8`** (six commits, 2026-07-05/06) — closed out the Codex-side dual-scope
   backlog items: G7-G13 (context packs, parallel dispatch, noisy-verification delegation,
   large-source digest paths), CX12-CX15 (Codex skill guidance + install smoke test + spawn
   break-even note), and the README-accuracy fixes (`/def` claim, Codex hook-wiring fallback,
   `.claude/` artifact ownership). All landed as `agents/codex/skills/less-tokens/SKILL.md` /
   `DOCUMENTATION.md` guidance plus one install-check test — no hook-enforced behavior changed.
   `BACKLOG.md` rows deleted, `CHANGELOG.md` entries added, per protocol.

## Open work
1. **Strategy 1 — calibrate the token estimate.** Run `stats.py --calibrate` once
   `ANTHROPIC_API_KEY` is available. Zero behavior risk, just needs the key.
2. **Strategy 3 Phase 1-2 / Strategy 4's threshold decision / the search.py-cache item** — all
   wait for real `near_misses.jsonl` data to accumulate from normal use. Do not guess at the
   numbers.
3. **G10 ID collision** — "G10" is reused for two unrelated entries across `BACKLOG.md` (declined
   "bound subagent search breadth") and `CHANGELOG.md` (shipped "search.py cross-file semantic
   dedup"). Confusing for anyone grepping by ID; needs one of them renamed. Low effort, still open.
4. **Missing acceptance criterion** — the "Same-session `search.py` repeated-query cache" backlog
   item has rich prose but no explicit "Acceptance:" line in the format other items use (e.g. G15's
   two-sentence criterion). Needs a measurable statement like "near_misses.jsonl records N
   identical-query events per session; repeat rate reported" before it's gradable pass/fail.
5. **G15 — propagate hooks into subagents (Claude side)** — done 2026-07-07: `SubagentStop` now
   wired alongside `Stop` for `caveman`/`savings-html` in `hook_manifest.py`. G14/G16/G17 also
   shipped the same day (new Claude `less-tokens` skill + `.claude/agents/{explorer,verifier}.md`).
   G15's Codex half found a real bug (relative-path hook commands break from a nested cwd) —
   filed to `BACKLOG.md`'s Bugs table, deferred to a Codex-context session.
6. **Separately flagged, not part of any plan above**: `test_hooks_protocol.py` grows real
   `.claude/state/savings.jsonl` on every run (`task_1b13bd51` if still live — check before
   re-flagging).

## Suggested skills
- `/bugfix` if a `near_misses.jsonl` review turns into an atomic fix.
- `/continue` — update this handoff again once calibration runs, the near-miss data is reviewed,
  or the G10/acceptance-criterion/G15 items move.

## Start here
Check `.claude/state/near_misses.jsonl` for accumulated real usage data before touching Strategy
3/4/5 again. If you're picking up G10 or the acceptance-criterion gap instead, those are pure
docs/BACKLOG edits — no data dependency, safe to do any time.

---
_Last updated at HEAD `f9214c8` on 2026-07-06, all work described above committed, nothing
pushed-status verified beyond local HEAD._
