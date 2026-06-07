# Backlog

Planned work not yet started. Maintainer: add `CHANGELOG.md` entry + delete item here before merging. See [.claude/skills/bug-hunt/SKILL.md](.claude/skills/bug-hunt/SKILL.md) / [.claude/skills/bug-hunt/bughuntlog.md](.claude/skills/bug-hunt/bughuntlog.md) for the bug-hunt protocol.

Token-reduction strategies and their rationale live in [evaluate.md](evaluate.md); unaddressed attack surfaces are catalogued in [gap.md](gap.md). Items below are tagged with their source `(evaluate.md)` / `(gap.md)`.

---

## Bugs

Confirmed defects found by code inspection. Each has a specific file and line reference.

_None open._

---

## Token-Reduction Strategies

Primary mission: fewer tokens. Ordered by impact × enforceability. Each item names the bucket it attacks: **input** (context read in), **output** (prose/code Claude writes), **tool** (tool-result dumps), **fixed** (paid every turn regardless of task), **meta** (multiplies the others). The **fixed** bucket is the biggest blind spot — barely touched beyond the just-shipped claudemd skill (see gap.md).

### High Priority

- **S13 — Grep-first Read gate (adopt former Strategy 7)** *(input)* — PreToolUse on `Read`: block files over a line threshold (default 150) read with no `offset`, telling Claude to locate first. Exempt files the shipped auto-slice hook already handles and search-first-gated indexed files (no double gate); route the locate step to the shipped symbol table (`symbols.py` / `/def`) rather than raw `grep -n`. S13 (with the shipped symbol index + auto-slice hook) completes the input pipeline: locate by symbol → read only the slice. Optionally log blocked Reads + lines saved via `.claude/tools/stats.py`. (evaluate.md; supersedes the old Strategy 7 sketch)

- **S10 — Post-Edit diff + block the re-Read** *(input)* — PostToolUse on `Edit`/`Write`: emit a tight unified diff (`git diff -U2` or difflib on before/after) so Claude sees the change without re-reading. PreToolUse on `Read`: if the file was edited within N seconds (track `STATE_DIR/last-edit`), block the verify re-Read. Replaces a full-file Read after every edit with a 2–10 line diff. (evaluate.md)

- **G2 — In-session re-read / re-search cache** *(input)* — PreToolUse content cache keyed on `(tool, args, file-mtime)`. On a repeat with unchanged inputs, block and return `"already in context (turn N) — unchanged since"` instead of re-injecting the payload. The general case of which S10 is the edit-specific slice; reuses the `STATE_DIR/last-search` plumbing. Distinct from the "query cache" cut in evaluate.md (that saved embedding compute; this stops re-injection into context). (gap.md)

- **G1 — Tool / MCP schema overhead** *(fixed)* — every tool/MCP schema sits in context on every turn; fat connectors can dwarf CLAUDE.md. Lazy tool exposure (load only what a task needs, fetch the rest on demand) + a `.toolignore` to drop unused servers from the session. Audit tool `.claude/tools/toolcost.py` estimates per-server schema tokens so the tax is visible. Enforcement is config-time (what loads), not a runtime hook. *Often the single largest untouched cost on real setups.* (gap.md)

- **G3 — Directory & listing dump control** *(tool)* — a scoped lister (depth-limited, `.gitignore`-aware, counts per dir instead of every file). PreToolUse on `Bash` detects bare `ls -R` / `find .` / `tree` and routes to it; cap `Glob` result count with an "N more" tail. Goes beyond truncation (S3), which keeps random head/tail of a still-noisy listing. (gap.md)

### Medium Priority

- **S12 — Structured tool-output parsers (skill)** *(tool)* — `.claude/skills/lean-output/` with parsers returning only signal: pytest → failing ids + assertion lines + counts; ruff/eslint → `file:line: code msg`; git → name-status + stat. PostToolUse on `Bash` auto-detects known tools and pipes through the parser before the result reaches context. Beats blind truncation (Strategy 3) — keeps the failing line, drops the noise. 60–95% on the noisiest, most-repeated outputs. (evaluate.md)

- **G6 — Live token governor** *(meta)* — a running session-token estimate (transcript size, already read by `compact-trigger.py`) that tightens knobs as the budget depletes: smaller `MAX_TOOL_OUTPUT_CHARS`, lower search `k`, earlier compaction, stricter caveman. One PostToolUse governor writes a live tier to state that the other hooks consult. Multiplies the existing strategies rather than adding a new surface. Supersedes the post-hoc, opt-in `stats.py` as a *live* control. (gap.md)

- **G9 — Always-loaded surfaces beyond CLAUDE.md** *(fixed)* — extend the claudemd approach: `claudemd_audit.py --rules` covers `.claude/rules/*`, and a `skilldesc_audit` flags bloated/overlapping skill descriptions (always-loaded, and they grow with the skill library) against a per-description word cap. Same budget + hook mechanism, wider scope. (gap.md)

### Low Priority

- **G5 — WebFetch main-content extraction** *(tool)* — a readability-style extractor (strip nav/footer/script) applied PostToolUse on `WebFetch` before the result reaches context. Returns the article body, not the chrome; avoids truncation cutting the part that mattered. Extends the S12 parser approach to web results. (gap.md)

- **G7 — Subagent context re-derivation** *(input)* — parent writes a compact context pack (relevant slices + search hits) to `STATE_DIR`; spawned agents read that instead of re-reading/re-searching the same files cold. Mostly a discipline + helper (a skill documenting "pass results, don't re-discover"); hard to hook-enforce. Spiky impact — large only when subagents are used heavily. (gap.md)

- **G8 — Don't reprint files in output** *(output)* — Stop-hook check (extends the shipped `caveman-reminder.py` Stop hook): flag a response containing a large code block whose content closely matches an existing file (line-overlap against the named path) and nudge `"use Edit, don't reprint <file>."` Caveman governs prose, not pasted code. (gap.md)

- **G10 — Search-result dedup** *(input)* — in `search.py`, drop a hit whose cosine to an already-selected hit exceeds a threshold and backfill the next distinct one, so overlapping/near-duplicate chunks aren't paid for twice per query. Pure post-processing on vectors already in hand; sharpens an existing strategy. (gap.md)

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
