# Backlog

Planned work not yet started. Maintainer: add `CHANGELOG.md` entry + delete item here before merging. See [.claude/skills/bug-hunt/SKILL.md](.claude/skills/bug-hunt/SKILL.md) / [.claude/skills/bug-hunt/bughuntlog.md](.claude/skills/bug-hunt/bughuntlog.md) for the bug-hunt protocol.

Token-reduction strategies and their rationale live in [evaluate.md](evaluate.md). Items below are tagged with their source `(evaluate.md)`.

---

## Bugs

Confirmed defects found by code inspection. Each has a specific file and line reference.

| **Bug** | **Details** | **Status** |
|---|---|---|
| **`symbols.py refresh()` ignores `--full` flag** | `full` parameter is accepted and documented but never consulted inside the function; always performs a full DELETE+reinsert regardless. `symbols.py:127` | open |
| **`caveman-reminder` counts unclosed code fence content as prose** | `_FENCE` regex requires a closing ` ``` `; an unclosed fence leaves code words in the prose word count, triggering false violation alerts. `caveman-reminder.py:67` | open |
| **`db.py connect_index()` return type annotation wrong** | Annotated `-> sqlite3.Connection` but returns `_ClosingConn`; suppressed with `# type: ignore[return-value]`; callers using the return value directly (outside `with`) get `AttributeError`. `db.py:55` | open |
| **`load_toolignore` keeps inline `#` comments as server names** | `"slack  # note"` is added verbatim to `ignored`; it never matches the settings key `"slack"`, so the server is never pruned. `mcp-prune.py:47` | open |
| **`mcp-prune._BASE` targets less_tokens dir, not host project** | `_BASE = Path(__file__).resolve().parent.parent.parent` resolves to the less_tokens source tree; `.toolignore` and `settings.json` are always looked up in the wrong directory when run from a host project. `mcp-prune.py:36` | open |
| **`total_tokens` undercounted due to per-row integer truncation** | `tok = sc // CHARS_PER_TOKEN` truncates per strategy; `sum(sc//4)` ≠ `sum(sc)//4`, so strategies saving fewer than 4 chars each contribute 0 tokens to the total. `stats.py:93` | open |
| **`_strip_code` unclosed fence leaks code into prose word count** | `re.sub(r"```.*?```", …)` only removes balanced fences; an unclosed ` ``` ` leaves its content in the prose, inflating filler/word counts and producing false `TRIM` verdicts. `claudemd_audit.py:94` | open |
| **`embed([])` crashes on empty section list, silently disabling dup check** | When CLAUDE.md has no headed sections `targets=[]`; `embed([])` produces a shape-`(0,)` array; `np.linalg.norm(axis=1)` raises `AxisError` caught by `except Exception → return None`, silently disabling duplicate detection. `claudemd_audit.py:196`, `embeddings.py:396` | open |

---

## Token-Reduction Strategies

Primary mission: fewer tokens. Ordered by impact × enforceability. Each item names the bucket it attacks: **input** (context read in), **output** (prose/code Claude writes), **tool** (tool-result dumps), **fixed** (paid every turn regardless of task), **meta** (multiplies the others). The **fixed** bucket is the biggest blind spot — barely touched beyond the just-shipped claudemd skill.

### High Priority

### Medium Priority

- **G9 — Always-loaded surfaces beyond CLAUDE.md** *(fixed)* — extend the claudemd approach: `claudemd_audit.py --rules` covers `.claude/rules/*`, and a `skilldesc_audit` flags bloated/overlapping skill descriptions (always-loaded, and they grow with the skill library) against a per-description word cap. Same budget + hook mechanism, wider scope.
### Low Priority

- **G5 — WebFetch main-content extraction** *(tool)* — a readability-style extractor (strip nav/footer/script) applied PostToolUse on `WebFetch` before the result reaches context. Returns the article body, not the chrome; avoids truncation cutting the part that mattered. Extends the S12 parser approach to web results.
- **G7 — Subagent context re-derivation** *(input)* — parent writes a compact context pack (relevant slices + search hits) to `STATE_DIR`; spawned agents read that instead of re-reading/re-searching the same files cold. Mostly a discipline + helper (a skill documenting "pass results, don't re-discover"); hard to hook-enforce. Spiky impact — large only when subagents are used heavily.
- **G8 — Don't reprint files in output** *(output)* — Stop-hook check (extends the shipped `caveman-reminder.py` Stop hook): flag a response containing a large code block whose content closely matches an existing file (line-overlap against the named path) and nudge `"use Edit, don't reprint <file>."` Caveman governs prose, not pasted code.
- **G10 — Search-result dedup** *(input)* — in `search.py`, drop a hit whose cosine to an already-selected hit exceeds a threshold and backfill the next distinct one, so overlapping/near-duplicate chunks aren't paid for twice per query. Pure post-processing on vectors already in hand; sharpens an existing strategy.
- **S6 — Tiered effort** *(output)* — route tasks to Haiku/Sonnet/Opus by need via `.claude/rules/tier-matrix.md` + an `AGENT_TIER_HINTS: bool` flag. **Verdict (evaluate.md): low confidence.** No hook can force a per-turn model downshift, so enforcement is weak and the claimed 50–70% blended saving is unverified. Keep as an opt-in rule only; prefer the shipped caveman Stop hook for output-token savings. (evaluate.md)

---

## Vector Search & Indexing

### High Priority

- **Configurable chunk size** — expose `MAX_CHUNK_CHARS` in `.claude/tools/search_config.py` so users can tune for their Claude model's context window
- **TypeScript / JavaScript chunking** — add a `chunk_js` strategy (function-level, like `chunk_python`) for projects with `.ts` / `.js` source

### Medium Priority

- **Implement graceful degradation** — explicit handlers in `.claude/tools/embeddings.py` and `.claude/tools/search.py` for each failure condition; each catches the failure, emits a structured warning to stderr, and continues rather than propagating an exception.

---

## Installer

### High Priority

- **`install.py --check`** — verify that a previous install is still valid: venv exists, fastembed is installed, `index.db` is present and has ≥1 row, `VENV_PY` resolves to a real interpreter, `.claude/hooks/*.py` exist and are executable, hooks are wired in `.claude/settings.json` (the file the installer actually writes — `install.py:1004`), and a `.claude/tools/search.py "test"` smoke query returns without error. Print `[✓]`/`[✗]` per check and exit non-zero with a specific message for each failure.
- **Auto-append caveman prompt to a resolved `CLAUDE.md` target** — `--caveman` copies `.claude/rules/` and wires the reminder hook, but appending the prompt to `CLAUDE.md` is left as a printed `cat .claude/rules/caveman.md >> CLAUDE.md` next-step (`install.py:1069-1070`). The reminder hook nags for terse output from the first turn even though the style spec it references is not yet in context. `_caveman_in_claude_md()` (`install.py:566`) already detects the duplicate — extend it to perform an idempotent append using guarded block markers (like the `.gitignore` block). Also resolve the ambiguous target: in a clone-into-host layout there are two `CLAUDE.md` files (host root vs `less_tokens/CLAUDE.md`), and `cat >>` against a missing host root file silently creates one containing only the caveman section with no `# CLAUDE.md` header. The installer should name the absolute target path and create a minimal valid `CLAUDE.md` (standard header) when absent. (`install.py:566`, `install.py:1064-1070`)
- **Wire the claudemd-budget hook** — `install.py` should deploy `.claude/hooks/claudemd-budget.py` and wire it as PostToolUse on `Edit|Write` in the host settings file, alongside the existing hooks. (Skill + tool + hook already built; installer wiring is the remaining step.)

---

## Hooks & Caveman Mode

### High Priority

- **Per-task exemptions** — allow CLAUDE.md to declare specific task types (e.g., user-facing copy, PR descriptions) that bypass caveman mode. Implement on the shipped caveman Stop hook (`caveman-reminder.py`) so its check honors the exemption list.

---

## Codex Agent

### High Priority

- **Wire `agentsmd-budget` PostToolUse hook for Codex** — `claudemd-budget.py` guards CLAUDE.md size for Claude but there is no counterpart for AGENTS.md under Codex. `agentsmd_audit.py` exists as a CLI tool but is never triggered automatically. Wire it as a PostToolUse on `Edit|Write` in `.codex/hooks.json` (and add it to `build_codex_hook_entries`) so AGENTS.md bloat is caught the same way CLAUDE.md bloat is caught for Claude.

- **Add prose word-count ceiling to `terse-reminder`** — the Codex `terse-reminder.py` (agents/codex/hooks) only pattern-matches filler phrases; it has no configurable `MAX_RESPONSE_WORDS` ceiling. The Claude `caveman-reminder.py` Stop hook has this. Add the same word-budget check to `terse-reminder` using `CODEX_MAX_RESPONSE_WORDS` (or share `MAX_RESPONSE_WORDS`) from `search_config.py`. `agents/codex/hooks/terse-reminder.py`

### Medium Priority

- **Symbol-lookup hint in Codex search-first hook** — the Claude `search-first.py` adds a non-blocking hint when a `Grep` pattern matches a known symbol (`"<name> is a known symbol — use symbols.py for exact location"`). The Codex `search-first.py` (agents/codex/hooks) omits this. Add the same hint so Codex users get the same locate-by-symbol affordance. `agents/codex/hooks/search-first.py`

---

## Developer Experience

### Low Priority

- **Consider GitHub self-hosted runners for the perf job** — the `perf` CI job downloads the fastembed model (~130 MB `BAAI/bge-small-en-v1.5`) and relies on `actions/cache`; a cold cache miss adds wall-clock time and network variance to timing results. A self-hosted runner with the model pre-installed in `~/.cache/huggingface` would remove both and give stable CPU baselines. Trade-off: infra maintenance + runner registration; only worth it if perf run times become a bottleneck or variance produces false failures. (Demoted: not on the token-reduction mission.)

---

## Removed (minimal impact — see evaluate.md)

Cut deliberately; they touch the periphery, not tokens spent. Recorded here so they are not re-proposed.

- **`search.py` interactive REPL** — exploratory-query DX, not token reduction.
- **`embeddings.py` file-watcher mode** — duplicates the existing PostToolUse refresh hook; DX, not token reduction.
- **Search quality metrics log** (`.claude/state/search.log`) — audit aid, saves no tokens.
- **`search.py` query history log** (`.claude/state/search-history.log`) — audit aid, saves no tokens.

---

## Bug-Hunt Protocol

### Current state (post-round-4)

- **Round 4** (7 surfaced; 6 real, 1 dismissed, 0 duplicate): silent ×3, ux ×2, cosmetic ×1. Overlap 0%. New files: `mcp-prune.py`, `stats.py`. Revisited: `install.py`, `claudemd_audit.py`, `embeddings.py`.
- **Severity slide**: ✗ — median ux both rounds (no drop).
- **Overlap rate**: ✗ — 0% (< 60%).
- **File coverage**: ✓ — ~85% (22/26 files, ≥ 80%).

**Verdict: keep hunting. 1 of 3 signals met; 4 files still unexplored (`claudemd-budget.py`, `model_profiles.py`, `savings_log.py`, `search_config.py`). Overlap still 0% — surface not yet saturated.**

### Previous state (post-round-3)

- **Round 3** (8 bugs surfaced; 8 real, 0 dismissed, 0 duplicate): silent ×3, ux ×3, cosmetic ×2. Overlap 0%. New files: `compact-trigger.py`, `search.py`, `lean-ls.py`, `post-edit-diff.py`, `symbols.py`, `caveman-reminder.py`, `db.py`.
- **Severity slide**: ✓ — median dropped from silent (R2) to ux (R3).
- **Overlap rate**: ✗ — 0% (< 60%).
- **File coverage**: ✗ — ~77% (20/26 files, < 80%).

**Verdict: keep hunting. 1 of 3 signals met; file coverage is 77% — one more round should push past 80% (6 files remain: `claudemd-budget.py`, `mcp-prune.py`, `model_profiles.py`, `savings_log.py`, `search_config.py`, `stats.py`).**

### Previous state (post-round-2)

- **Round 2** (10 bugs surfaced; 10 real, 0 dismissed, 0 duplicate): silent ×7, ux ×3. Overlap 0%. New files: `truncate-output.py`, `read-after-edit.py`, `read-guard.py`, `search-first.py`, `index-refresh.py`, `claudemd_audit.py`, `listing-guard.py`, `toolcost.py`.
- **Severity slide**: ✗ — median silent both rounds (no drop).
- **Overlap rate**: ✗ — 0% (< 60%).
- **File coverage**: ✗ — ~50% (13/26 files, < 80%).

**Verdict: keep hunting.**

### Previous state (post-round-1)

- **Round 1** (7 bugs surfaced; 7 real, 0 dismissed, 0 duplicate): silent ×5, ux ×2, cosmetic ×1. Overlap 0%. Files hit: `embeddings.py`, `install.py`, `auto-slice.py`, `grep-first-read.py`, `context-cache.py` (5 of ~26 source files).
- **Severity slide**: ✗ — Round 1, no prior round to compare.
- **Overlap rate**: ✗ — 0% (< 60%).
- **File coverage**: ✗ — ~19% (5/26 files, < 80%).

**Verdict: keep hunting.**
