# Backlog

Planned work not yet started. Maintainer: add `CHANGELOG.md` entry + delete item here before merging. See [bughunt/bughunt.md](bughunt/bughunt.md) / [bughunt/bughuntlog.md](bughunt/bughuntlog.md) for the bug-hunt protocol.

---

## Bugs

Confirmed defects found by code inspection. Each has a specific file and line reference.

---

## Vector Search & Indexing

### High Priority

- **Multi-repo indexing** — support indexing across multiple project roots so a single search spans related repos (monorepo support)
- **Configurable chunk size** — expose `MAX_CHUNK_CHARS` in `search_config.py` so users can tune for their Claude model's context window
- **TypeScript / JavaScript chunking** — add a `chunk_js` strategy (function-level, like `chunk_python`) for projects with `.ts` / `.js` source

### Medium Priority

- **Keyword fallback** — when `fastembed` is not installed or the model download fails, fall back to a stdlib BM25/TF-IDF search over raw chunk text. Quality is lower but the system remains usable before the model cache is warm. Exit code and output format identical to normal search so hooks require no changes.
- **Implement graceful degradation** — explicit handlers in `tools/embeddings.py` and `tools/search.py` for each failure condition; each catches the failure, emits a structured warning to stderr, and continues rather than propagating an exception.

### Low Priority

- **Remote index option** — store `index.db` in S3 / R2 for teams sharing an index across machines
- **`search.py` interactive REPL** — `search.py --interactive` for rapid exploratory querying during development
- **`embeddings.py` file-watcher mode** — a `watch` subcommand using `watchdog` that monitors `INDEXED_SOURCE_DIRS` and triggers incremental refresh automatically on save, as an alternative to the PostToolUse hook

---

## Installer

### High Priority

- **Auto-patch `INDEXED_SOURCE_DIRS` in `search_config.py`** — `VENV_PY` is now auto-patched after venv detection (`install.py:955`), but `INDEXED_SOURCE_DIRS` is left at the less_tokens defaults (`tools/`, `schema/`), not the host's source dirs. Scan the host repo for directories containing `.py` files and patch in place (or prompt with the discovered list). The next-steps output should also explain the `INDEXED_SOURCE_DIRS` (`.py`/`.sql`) vs `INDEXED_ROOT_GLOBS` (`.md`) split so users of non-Python repos know which variable to edit.
- **Recursive-glob guidance for doc-heavy repos** — `INDEXED_ROOT_GLOBS` defaults to `("*.md",)` evaluated via non-recursive `BASE.glob` (`tools/embeddings.py:180`), so a repo whose docs live in `docs/`, `.agents/`, etc. indexes none of them. `pathlib` does support `**`, but nothing tells the user. Add a `# supports recursive patterns, e.g. "docs/**/*.md"` comment in `search_config.py`, surface `INDEXED_ROOT_GLOBS` in the next-steps output, and if the installer finds no `.py` files but many subdirectory `.md` files, suggest recursive globs.
- **`install.py --update`** — re-copy hook and tool files without touching `search_config.py` or `index.db` (safe upgrade path)
- **`install.py --check`** — verify that a previous install is still valid: venv exists, fastembed is installed, `index.db` is present and has ≥1 row, `VENV_PY` resolves to a real interpreter, `.claude/hooks/*.py` exist and are executable, hooks are wired in `.claude/settings.json` (the file the installer actually writes — `install.py:1004`), and a `tools/search.py "test"` smoke query returns without error. Print `[✓]`/`[✗]` per check and exit non-zero with a specific message for each failure.
- **Auto-append caveman prompt to a resolved `CLAUDE.md` target** — `--caveman` copies `caveman/` and wires the reminder hook, but appending the prompt to `CLAUDE.md` is left as a printed `cat caveman/caveman.md >> CLAUDE.md` next-step (`install.py:1069-1070`). The reminder hook nags for terse output from the first turn even though the style spec it references is not yet in context. `_caveman_in_claude_md()` (`install.py:566`) already detects the duplicate — extend it to perform an idempotent append using guarded block markers (like the `.gitignore` block). Also resolve the ambiguous target: in a clone-into-host layout there are two `CLAUDE.md` files (host root vs `less_tokens/CLAUDE.md`), and `cat >>` against a missing host root file silently creates one containing only the caveman section with no `# CLAUDE.md` header. The installer should name the absolute target path and create a minimal valid `CLAUDE.md` (standard header) when absent. (`install.py:566`, `install.py:1064-1070`)

### Medium Priority

- **Build the index during install by default** — the `--build` flag exists (`install.py:823`, runs `build_index`) and is documented, but a default install leaves no `index.db`, so `tools/search.py` returns empty until the user runs the build manually (the first run also downloads the fastembed model). Make the build run by default with an opt-out, or interactively prompt `Build the index now? ~30s on first run (model download). [Y/n]` — so the install completes in one step instead of two.
---

## Hooks & Caveman Mode

### High Priority

- **Calibrated verbosity levels** — replace binary caveman on/off with a 1–5 verbosity dial in `search_config.py`; level 1 = full caveman, level 5 = normal prose
- **Per-task exemptions** — allow CLAUDE.md to declare specific task types (e.g., user-facing copy, PR descriptions) that bypass caveman mode

---

## Observability

### Medium Priority

- **Search quality metrics** — log query, top result score, and result count to `.claude/state/search.log` so users can audit what Claude is finding
- **`search.py` query history log** — append each query and its top result score to `.claude/state/search-history.log` so maintainers can audit what Claude searched for and identify queries that consistently return poor results
- **Dashboard command** — `embeddings.py stats --verbose` showing index age, chunk count by source type, and estimated coverage

---

## Developer Experience

### Medium Priority

- **Consider GitHub self-hosted runners for the perf job** — the `perf` CI job downloads the fastembed model (~130 MB `BAAI/bge-small-en-v1.5`) and relies on `actions/cache` for subsequent runs; a cold cache miss adds significant wall-clock time and introduces network variance into timing results. A self-hosted runner with the model pre-installed in `~/.cache/huggingface` would eliminate both the download and the cache-restore step, and would provide stable CPU baselines so reduction-percentage regressions aren't masked by runner noise. Trade-off: self-hosted runners require infrastructure maintenance and the runner must be registered to the repo; only worth the overhead if perf run times become a bottleneck or timing variance starts producing false failures.

---

## Proposed Strategies

### Strategy 6 — Tiered Effort

Route each task to the cheapest Claude model + effort level it needs. Three tiers: **L1 Mechanical** (Haiku, one confirmation, no summaries), **L2 Rules** (Sonnet, result + brief reasoning), **L3 Planning** (Opus, full analysis). Before each task the agent emits one line with the recommended tier only when it changes from the prior turn. Implementation: `caveman/tier-matrix.md` appended to `CLAUDE.md` + `AGENT_TIER_HINTS: bool` config flag. Expected savings: 50–70% blended reduction.

### Strategy 4 — Prompt Caching *(deferred — likely redundant with Claude Code defaults)*

Claude Code already caches the system prompt and `CLAUDE.md` automatically. Revisit if measurement on a real session shows the auto-cache is missing large doc files Claude reads every turn.
