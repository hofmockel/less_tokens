# Continue: less_tokens

> **Next focus:** `BACKLOG.md` **Ready now** is empty; **Next** table top item is **P4** (order 12,
> P2, Ready) — generate installer flag docs from `argparse` metadata, a well-scoped doc-drift fix.
> If a P1 is preferred instead, pick from **Blocked / evidence collection** once its unblock
> signal fires, or scope a **Next**-table item into Ready.

## Current state

Working tree clean, `main` is 1 commit ahead of `origin/main` (`6516256`, **not yet pushed**) —
push before starting new work. `BACKLOG.md` **Ready now** is empty; the **Next** table (order
12–22) is the queue. PC1 shipped and closed this session.

## What happened this session (2026-07-23)

- Shipped **PC1** — prompt-cache health now reported from native transcript usage records, not
  inferred from size. New `agents/common/cache_health.py`: parses Claude's `message.usage` and
  Codex's `token_count` event records per the per-platform formulas already verified in
  `DECISIONS.md`'s PC1 entry (Claude and Codex define `input_tokens` differently — a shared
  cache-read-share formula would double-count). Resolved both open design questions that had
  blocked implementation:
  - **Transcript discovery.** Claude is deterministic, not a filesystem search: the hook payload's
    native `session_id` field *is* the transcript filename stem — verified against a live
    transcript, whose own `sessionId` field matched exactly — so
    `~/.claude/projects/<slugify(cwd)>/<session_id>.jsonl` needs no guessing. Falls back to
    newest-mtime in the slug directory only when no payload-sourced session_id is on hand. Codex,
    as `DECISIONS.md` already anticipated, isn't cwd-organized: resolved via a `cwd`-field grep
    across recent `rollout-*.jsonl` files, explicitly skipping nested subagent rollouts
    (`thread_source == "subagent"`) which share the parent's cwd but aren't "the session."
  - **Abrupt-miss-window rule.** A cache-read share dropping ≥30 points off a ≥70%-warm trailing
    5-turn baseline. This is a named, centralized initial estimate (`ABRUPT_MISS_*` constants in
    `cache_health.py`) — no calibration corpus exists yet to validate the exact thresholds against
    a real cache-miss event; revisit once D4's benchmark work or real telemetry surfaces one.
  - Version gating follows the existing `hook_manifest.py` pattern (`parse_version`/window-tuple
    check): Claude 2.1.181–2.1.215, Codex reads from 0.142.3, Codex `cache_write_input_tokens`
    only from 0.145.0 — reported `unavailable`, never zero, outside these windows.
  - Wired into `stats.py`'s Markdown and HTML reports as a new "Prompt-cache health" panel, kept
    separate from the strategy-savings tables (different data source entirely; no schema change to
    `savings.jsonl` was needed — cwd + already-stored session_id/session_source was enough).
- Verified end-to-end against a **live** Codex transcript on this machine (not a fixture): 69
  turns, 91.9% average cache-read share, zero abrupt-miss windows, `cache_write_input_tokens`
  correctly reported `unavailable` (local Codex is 0.144.6, below the 0.145.0 floor). The Claude
  path is verified deterministically (slug algorithm and `session_id`-matches-filename both
  confirmed against real files on disk) but **not** exercised end-to-end this session — no `claude`
  binary was on the verifying shell's `PATH` to fetch `--version`, so it correctly reported
  `unavailable` rather than guessing a version.
- New tests: `.claude/tests/unit/test_cache_health.py` (20 cases). Full suite: `dev.py unit`
  equivalent (`pytest .claude/tests`) — 1242 passed.
- `CHANGELOG.md` `[Unreleased]` entry added; `DECISIONS.md`'s PC1 entry updated from "neither
  design question is designed yet" to the resolutions above; `PC1` row and prose deleted from
  `BACKLOG.md`.
- Not done this session, deliberately out of scope: Claude-path live verification (needs a shell
  with `claude` on `PATH`), and calibrating the abrupt-miss constants against a real observed miss
  (needs a live incident or D4's benchmark corpus, neither exists yet).

## Open work

See [BACKLOG.md](BACKLOG.md) **Next** table, order 12 onward — all P2, all Ready (no Research
items queued right now). **Blocked / evidence collection** holds C1/SA3/SA4/SA5, each waiting on a
telemetry signal described inline; don't start those until the unblock condition is actually met.

## Suggested skills

- `/bug-hunt` — hasn't run this session; worth a sweep before picking a doc-only item, in case it
  surfaces something sharper than the Next-table order.
- `/bugfix` — if a bug-hunt turns up something bugfix-shaped rather than backlog-shaped.

## Start here

**Push `main` first** (`git push`) and confirm no one else pushed to `origin/main` in the
meantime (this repo has a history of parallel local/origin divergence — see prior continue.md
reconciliation notes in git history if `git push` rejects). Then read `BACKLOG.md`'s **Next**
table top-to-bottom and pick the first item whose acceptance criteria fit the time available; P4
(installer flag docs) is the top of the queue and well-scoped if no stronger preference exists.

---
_Last updated at HEAD `6516256` (1 ahead of `origin/main`, unpushed) on 2026-07-23._
