# Continue: less_tokens

> **Next focus:** everything actionable right now is either instrument-first (blocked on real
> `near_misses.jsonl` usage data) or handed off to a Codex-context session (the nested-cwd hook bug).
> No open Claude-side code work — remaining items are pure docs/BACKLOG edits or data review.

## Current state
HEAD is `be7eddc`, repo clean, 914/914 tests pass. G14-G17 (the Claude-side subagent
token-reduction items) shipped this session — Codex already had its equivalents (G7-G13,
CX12-CX15) from the prior session ending at `f9214c8`.

## What happened this session
- **G15** — wired `SubagentStop` alongside `Stop` for `caveman-reminder.py`/`savings-html.py` in
  `agents/common/hooks/hook_manifest.py` (single source of truth feeding both `install.py` and this
  repo's own dogfooded `.claude/settings.json`). Both scripts already read `transcript_path` off
  stdin without inspecting `hook_event_name`, so no script changes were needed — just the wire.
- **G14/G16/G17** — built a full Claude-side `less-tokens` skill
  (`agents/claude/skills/less-tokens/SKILL.md`, mirrors the existing Codex one) plus two narrow
  agent-definition files, `.claude/agents/explorer.md` (Read/Grep/Glob only) and `verifier.md`
  (Bash/Read only), installed via new `install.py` copy steps. This closes the "Claude has no
  skill to hang subagent guidance on" gap the three items shared.
- **Found, filed, not fixed**: `.codex/hooks.json` commands use a relative path
  (`.less_tokens/bin/python ...`) that resolves from repo root but fails silently (exit 127) from
  any other cwd — confirmed by installing into a scratch repo and invoking the command from a
  nested subdirectory. Per hofmockel's explicit call, this is Codex's fix to make, not this
  session's — filed to `BACKLOG.md`'s Bugs table instead of touched.
- Also: moved F3 (terse hook block messages, already marginal) from `BACKLOG.md` to `DECISIONS.md`
  as rejected, closing a low-priority item with no path to closure otherwise.

## Open work
See [BACKLOG.md](BACKLOG.md). Nothing here is Claude-side-blocked:
1. **Codex nested-cwd bug** (Bugs table) — needs a Codex-context session; likely fix is
   absolute-path `.codex/hooks.json` commands (Claude's `.claude/settings.json` stays relative,
   the harness already resets Bash cwd to repo root between calls).
2. **Strategy 1** — run `stats.py --calibrate` once `ANTHROPIC_API_KEY` is available.
3. **Strategy 3/4/5 + search.py-cache item** — all wait for `near_misses.jsonl` to accumulate more
   real usage. Do not guess at the numbers.
4. **G10 ID collision** and **missing acceptance criterion** on the search-cache item — both pure
   docs/BACKLOG edits, low effort, no data dependency.

## Suggested skills
- `/bugfix` if the Codex nested-cwd bug gets picked up, or a `near_misses.jsonl` review turns into
  an atomic fix.
- `/continue` — rewrite this once the Codex bug lands, calibration runs, or near-miss data is reviewed.

## Start here
If in a Codex-context session: fix the nested-cwd hook-command bug (`BACKLOG.md` Bugs table has
full repro). Otherwise: check `.claude/state/near_misses.jsonl` for accumulated data before
touching Strategy 3/4/5, or pick up G10/acceptance-criterion (no data dependency, safe any time).

---
_Last updated at HEAD `be7eddc` on 2026-07-07._
