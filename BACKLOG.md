# Backlog

Planned work not yet started. Maintainer: add `CHANGELOG.md` entry + delete item here before merging. See [.claude/skills/bug-hunt/SKILL.md](.claude/skills/bug-hunt/SKILL.md) / [.claude/skills/bug-hunt/bughuntlog.md](.claude/skills/bug-hunt/bughuntlog.md) for the bug-hunt protocol.

Token-reduction strategies and their rationale live in [evaluate.md](evaluate.md). Items below are tagged with their source `(evaluate.md)`.

---

## Bugs

Confirmed defects found by code inspection. Each has a specific file and line reference.

| **Bug** | **Details** | **Status** |
|---|---|---|

---

## Token-Reduction Strategies

Primary mission: fewer tokens. Ordered by impact × enforceability. Each item names the bucket it attacks: **input** (context read in), **output** (prose/code Claude writes), **tool** (tool-result dumps), **fixed** (paid every turn regardless of task), **meta** (multiplies the others). The **fixed** bucket is the biggest blind spot — barely touched beyond the just-shipped claudemd skill.

### High Priority

### Medium Priority

- **G9 — Always-loaded surfaces beyond CLAUDE.md** *(fixed)* — extend the claudemd approach: `claudemd_audit.py --rules` covers `.claude/rules/*`, and a `skilldesc_audit` flags bloated/overlapping skill descriptions (always-loaded, and they grow with the skill library) against a per-description word cap. Same budget + hook mechanism, wider scope.
### Low Priority

- **G7 — Subagent context re-derivation** *(input)* — parent writes a compact context pack (relevant slices + search hits) to `STATE_DIR`; spawned agents read that instead of re-reading/re-searching the same files cold. Mostly a discipline + helper (a skill documenting "pass results, don't re-discover"); hard to hook-enforce. Spiky impact — large only when subagents are used heavily.

- **G10 — Search-result dedup** *(input)* — in `search.py`, drop a hit whose cosine to an already-selected hit exceeds a threshold and backfill the next distinct one, so overlapping/near-duplicate chunks aren't paid for twice per query. Pure post-processing on vectors already in hand; sharpens an existing strategy.
- **S6 — Tiered effort** *(output)* — route tasks to Haiku/Sonnet/Opus by need via `.claude/rules/tier-matrix.md` + an `AGENT_TIER_HINTS: bool` flag. **Verdict (evaluate.md): low confidence.** No hook can force a per-turn model downshift, so enforcement is weak and the claimed 50–70% blended saving is unverified. Keep as an opt-in rule only; prefer the shipped caveman Stop hook for output-token savings. (evaluate.md)

---

## Vector Search & Indexing

### High Priority

---

## Installer

### High Priority

- **Auto-append caveman prompt to a resolved `CLAUDE.md` target** — `--caveman` copies `.claude/rules/` and wires the reminder hook, but appending the prompt to `CLAUDE.md` is left as a printed `cat .claude/rules/caveman.md >> CLAUDE.md` next-step (`install.py:1069-1070`). The reminder hook nags for terse output from the first turn even though the style spec it references is not yet in context. `_caveman_in_claude_md()` (`install.py:566`) already detects the duplicate — extend it to perform an idempotent append using guarded block markers (like the `.gitignore` block). Also resolve the ambiguous target: in a clone-into-host layout there are two `CLAUDE.md` files (host root vs `less_tokens/CLAUDE.md`), and `cat >>` against a missing host root file silently creates one containing only the caveman section with no `# CLAUDE.md` header. The installer should name the absolute target path and create a minimal valid `CLAUDE.md` (standard header) when absent. (`install.py:566`, `install.py:1064-1070`)
- **Wire the claudemd-budget hook** — `install.py` should deploy `.claude/hooks/claudemd-budget.py` and wire it as PostToolUse on `Edit|Write` in the host settings file, alongside the existing hooks. (Skill + tool + hook already built; installer wiring is the remaining step.)

---

## Hooks & Caveman Mode

---

## Codex Agent

### High Priority

- **Wire `agentsmd-budget` PostToolUse hook for Codex** — `claudemd-budget.py` guards CLAUDE.md size for Claude but there is no counterpart for AGENTS.md under Codex. `agentsmd_audit.py` exists as a CLI tool but is never triggered automatically. Wire it as a PostToolUse on `Edit|Write` in `.codex/hooks.json` (and add it to `build_codex_hook_entries`) so AGENTS.md bloat is caught the same way CLAUDE.md bloat is caught for Claude.

- **Add prose word-count ceiling to `terse-reminder`** — the Codex `terse-reminder.py` (agents/codex/hooks) only pattern-matches filler phrases; it has no configurable `MAX_RESPONSE_WORDS` ceiling. The Claude `caveman-reminder.py` Stop hook has this. Add the same word-budget check to `terse-reminder` using `CODEX_MAX_RESPONSE_WORDS` (or share `MAX_RESPONSE_WORDS`) from `search_config.py`. `agents/codex/hooks/terse-reminder.py`

- **`terse-reminder` filler threshold too permissive** — Codex fires only after 2+ filler hits (`MIN_FILLER_HITS = 2`, simple string match); Claude's `caveman-reminder.py` fires on any single regex match. Same config, different strictness. Drop `MIN_FILLER_HITS` to 1 and switch to the same compiled-regex patterns used by `caveman-reminder.py`. `agents/codex/hooks/terse-reminder.py`

### Medium Priority

- **Symbol-lookup hint in Codex search-first hook** — the Claude `search-first.py` adds a non-blocking hint when a `Grep` pattern matches a known symbol (`"<name> is a known symbol — use symbols.py for exact location"`). The Codex `search-first.py` (agents/codex/hooks) omits this. Add the same hint so Codex users get the same locate-by-symbol affordance. `agents/codex/hooks/search-first.py`

- **No `agentsmd` skill for Codex** — the `claudemd` skill guides manual pruning of CLAUDE.md bloat; there is no counterpart skill for AGENTS.md. `agentsmd_audit.py` exists as a CLI but is not surfaced as an invokable skill. Add `agents/codex/skills/agentsmd/SKILL.md` mirroring the `claudemd` skill structure. `agents/codex/skills/`

- **No `stop_hook_active` guard in `terse-reminder`** — `caveman-reminder.py` checks `payload.get("stop_hook_active")` and bails to prevent an infinite re-prompt loop. `terse-reminder.py` has no such guard. Add the same check. `agents/codex/hooks/terse-reminder.py`

### Low Priority

- **No Codex port for `listing-guard` and `read-guard`** — both hooks are tool-agnostic (guard against reading noise files and large directory listings) but are only wired for Claude. Port to `agents/codex/hooks/` and add to `build_codex_hook_entries` in `install.py`.

---

## Developer Experience

### Low Priority

- **Consider GitHub self-hosted runners for the perf job** — the `perf` CI job downloads the fastembed model (~130 MB `BAAI/bge-small-en-v1.5`) and relies on `actions/cache`; a cold cache miss adds wall-clock time and network variance to timing results. A self-hosted runner with the model pre-installed in `~/.cache/huggingface` would remove both and give stable CPU baselines. Trade-off: infra maintenance + runner registration; only worth it if perf run times become a bottleneck or variance produces false failures. (Demoted: not on the token-reduction mission.)

---