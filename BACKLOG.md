# Backlog

Planned work not yet started. Maintainer: add `CHANGELOG.md` entry + delete item here before merging. See [bughunt.md](bughunt.md) / [bughuntlog.md](bughuntlog.md) for the bug-hunt protocol.

---

## Bugs

Confirmed defects found by code inspection. Each has a specific file and line reference.

- **`start_new_session=True` is a no-op on Windows in `index-refresh.py`** — `subprocess.Popen(..., start_new_session=True)` is documented as POSIX-only; on Windows the kwarg is ignored and the child remains attached to the parent, defeating the detach intent. Fix: branch on `sys.platform`; on Windows pass `creationflags=subprocess.DETACHED_PROCESS` (or `CREATE_NEW_PROCESS_GROUP`) instead. (`hooks/index-refresh.py:72`)

- **Venv path containing `"` produces invalid Python in the printed `VENV_PY` line** — `f'       VENV_PY = _venv_python("{venv_dir}")'` interpolates the path raw; a path with an embedded `"` yields a `SyntaxError` when the user pastes it. Fix: emit `repr(str(venv_dir))` or `json.dumps(str(venv_dir))` so escaping is correct. (`install.py:189-190`)

- **`--source-type` argparse `choices` may drift from values actually stored in `documents.source_type`** — argparse rejects valid values present in older databases (or accepts values no longer produced) because the choices list and the column are two unsynchronised sources of truth. Fix: derive choices from `SELECT DISTINCT source_type FROM documents` at runtime, or add a `CHECK` constraint to `index.sql` that pins the vocabulary. (`tools/search.py:70`)

- **Vectors stored in native byte order — `index.db` is not portable across endianness** — `np.float32.tobytes()` writes host-native bytes; `np.frombuffer(..., dtype=np.float32)` reads with the host's endianness. A db built on little-endian and read on big-endian (POWER, s390x, some embedded ARM) returns silently wrong cosine scores. Fix: pin dtype to `<f4` (little-endian) on both write and read paths. (`tools/embeddings.py:296`, `tools/search.py:46`)

- **`enumerate_sources()` aborts the entire refresh on a single permission-denied directory** — `path.rglob("*")` propagates `PermissionError` from a single unreadable subtree, killing the run and leaving the index stale. Fix: wrap each per-source enumeration in `try/except OSError`, log a warning, and continue. (`tools/embeddings.py:173`)

- **Heading-dedup `_2` suffix can collide with a literal `## Foo_2` in the same file** — the dedup logic renames repeats to `Foo_2`, but if the source already contains `## Foo_2` literally, both end up with identical `(source_path, source_key)` and the UPSERT silently overwrites. Fix: pre-scan all heading keys for the file and only suffix when the candidate is free, or use an ordinal scheme (`Foo#2`) using a character that cannot appear in a markdown heading. (`tools/embeddings.py:94-99`)

---

## Vector Search & Indexing

### High Priority

- **Multi-repo indexing** — support indexing across multiple project roots so a single search spans related repos (monorepo support)
- **Stale index warning** — detect when indexed files have changed since last refresh and surface a warning in `search.py` output before results
- **Configurable chunk size** — expose `MAX_CHUNK_CHARS` in `search_config.py` so users can tune for their Claude model's context window
- **TypeScript / JavaScript chunking** — add a `chunk_js` strategy (function-level, like `chunk_python`) for projects with `.ts` / `.js` source
- **Move `MODEL` and `DIM` to `search_config.py`** — replace the hardcoded constants in `embeddings.py:39-40` with config variables so users can switch embedding models without editing tool source. `search.py` must read `DIM` from config (or from the stored `embedding_model` row) rather than a hardcoded literal. (`tools/embeddings.py:39-40`, `tools/search.py:44`)
- **`search.py --min-score`** — add a score threshold flag (e.g. `--min-score 0.5`) to filter out low-confidence results; prevents Claude from acting on semantically unrelated chunks that happen to rank in the top-k

### Medium Priority

- **`search.py` result deduplication** — when two top-k results come from the same `source_path`, collapse them into one entry and use the saved tokens for an additional unique file; avoids spending context budget on near-duplicate chunks
- **Multi-file chunk context** — when returning a function chunk, optionally prepend the containing class or module docstring so Claude has the structural context needed to understand the chunk without a follow-up Read
- **`embeddings.py refresh --dry-run`** — show which chunks would be added, updated, or deleted without writing to `index.db`; useful for verifying config changes before committing
- **`embeddings.py switch-model`** — a subcommand that changes `EMBEDDING_MODEL` in `search_config.py` and immediately runs `refresh --full`, preventing the silent dimension mismatch that occurs when the model is changed manually. Prints a clear warning about re-index time before proceeding.
- **Keyword fallback** — when `fastembed` is not installed or the model download fails, fall back to a stdlib BM25/TF-IDF search over raw chunk text. Quality is lower but the system remains usable before the model cache is warm. Exit code and output format identical to normal search so hooks require no changes.
- **Implement graceful degradation** — explicit handlers in `tools/embeddings.py` and `tools/search.py` for each failure condition; each catches the failure, emits a structured warning to stderr, and continues rather than propagating an exception.
- **`AGENT_MODEL` config variable** — add an optional `AGENT_MODEL` string to `search_config.py` (e.g. `"claude-sonnet-4-6"`). When set, `search.py` uses a lookup table to select default `k` and warn if chunks risk filling the window. When unset, current defaults apply unchanged.
- **Context-window lookup table** — ship `tools/model_profiles.py` mapping Claude model IDs (Haiku / Sonnet / Opus) to context window size and recommended `k` / `MAX_CHUNK_CHARS` values.

### Low Priority

- **Remote index option** — store `index.db` in S3 / R2 for teams sharing an index across machines
- **`search.py` interactive REPL** — `search.py --interactive` for rapid exploratory querying during development
- **`embeddings.py` file-watcher mode** — a `watch` subcommand using `watchdog` that monitors `INDEXED_SOURCE_DIRS` and triggers incremental refresh automatically on save, as an alternative to the PostToolUse hook

---

## Installer

### High Priority

- **Auto-update `search_config.py`** — after detecting the venv, patch `VENV_PY` and `INDEXED_SOURCE_DIRS` in place rather than just printing the line
- **`install.py --update`** — re-copy hook and tool files without touching `search_config.py` or `index.db` (safe upgrade path)
- **`install.py --check`** — verify that a previous install is still valid: venv exists, fastembed is installed, `index.db` is present, hooks are wired in `settings.local.json`; exits non-zero with a specific message for each failure
- **`VIRTUAL_ENV` environment variable fallback in venv detection** — `detect_venv()` in `install.py` and `_venv_python()` in `search_config.py` should check the `VIRTUAL_ENV` env var first, since it's set by `activate` and reliably points to the active venv on all platforms

---

## Hooks & Caveman Mode

### High Priority

- **Expose `WINDOW_SECONDS` in `search_config.py`** — the 5-minute search-gate window is hardcoded in `search-first.py`; moving it to `search_config.py` lets users tune the aggressiveness of the gate without editing hook source code
- **Calibrated verbosity levels** — replace binary caveman on/off with a 1–5 verbosity dial in `search_config.py`; level 1 = full caveman, level 5 = normal prose
- **Per-task exemptions** — allow CLAUDE.md to declare specific task types (e.g., user-facing copy, PR descriptions) that bypass caveman mode

---

## Observability

### Medium Priority

- **Search quality metrics** — log query, top result score, and result count to `.claude/state/search.log` so users can audit what Claude is finding
- **`search.py` query history log** — append each query and its top result score to `.claude/state/search-history.log` so maintainers can audit what Claude searched for and identify queries that consistently return poor results
- **Token savings estimate** — after each search, print an estimated token delta vs. reading all matched files in full
- **Dashboard command** — `embeddings.py stats --verbose` showing index age, chunk count by source type, and estimated coverage

---

## Developer Experience

### Medium Priority

- **Consider GitHub self-hosted runners for the perf job** — the `perf` CI job downloads the fastembed model (~130 MB `BAAI/bge-small-en-v1.5`) and relies on `actions/cache` for subsequent runs; a cold cache miss adds significant wall-clock time and introduces network variance into timing results. A self-hosted runner with the model pre-installed in `~/.cache/huggingface` would eliminate both the download and the cache-restore step, and would provide stable CPU baselines so reduction-percentage regressions aren't masked by runner noise. Trade-off: self-hosted runners require infrastructure maintenance and the runner must be registered to the repo; only worth the overhead if perf run times become a bottleneck or timing variance starts producing false failures.
- **`pre-commit` config** — add `ruff` and `pyright` hooks so contributors get linting feedback before pushing

---

## Documentation

### High Priority

- **No troubleshooting section in README** — the three most common failure modes (fastembed download fails on first run, wrong venv path in `search_config.py`, empty index returning no results) have no documented recovery steps anywhere

### Medium Priority

- **README shows separate JSON blocks for each hook** — the wiring section presents each hook in its own `settings.local.json` snippet; users must manually merge them and JSON merging is a common source of errors; show one complete unified block
- **`index-refresh.log` is never mentioned** — background refresh writes to `.claude/state/index-refresh.log` but this path appears nowhere in the README or tool help text; users have no way to diagnose silent refresh failures without reading source code
- **`embeddings.py` module docstring uses `python3` in usage examples** — lines 13–16 show `python3 tools/embeddings.py refresh` which doesn't work on Windows and ignores the venv requirement; should use `<venv-python> tools/embeddings.py refresh`
- **CONTRIBUTING.md says "test manually" with no specifics** — the verification step doesn't describe what a passing manual test looks like; should list the concrete commands to run (`install.py`, `search_config.py` edit, `refresh`, `search.py`, hook fire)
- **`search_config.py` inline comment for `EXCLUDED_DIR_PREFIXES` doesn't explain the difference from `EXCLUDED_DIR_NAMES`** — both variables exclude directories but via different mechanisms (prefix match on full path vs. bare name match on any path component); the distinction trips up new users when their exclusions don't work as expected
- **README doesn't document `WINDOW_SECONDS` or how to change it** — the 5-minute search-gate window is mentioned in passing but there's no explanation that it's hardcoded or where to change it
- **No explanation of what Claude does when `search.py` returns no results** — the README mentions the fallback conditions for using `Read` directly but doesn't explain whether the gate is automatically lifted or whether Claude must explicitly detect the empty result
- **CHANGELOG uses Keep a Changelog version format but `chunk_changelog` expects date-only headers** — there is no note in the CHANGELOG or in `embeddings.py` that the chunker's date-pattern regex won't match the `## [version] - date` format; developers adding changelog entries won't know the index is silently not splitting them correctly

### Low Priority

- **Animated GIF demo** — screencast showing a before/after: full Read vs. search returning targeted chunks
- **Token savings benchmarks** — documented measurements on a real codebase showing actual input/output token reduction

---

## Proposed Strategies

### Strategy 6 — Tiered Effort

Route each task to the cheapest Claude model + effort level it needs. Three tiers: **L1 Mechanical** (Haiku, one confirmation, no summaries), **L2 Rules** (Sonnet, result + brief reasoning), **L3 Planning** (Opus, full analysis). Before each task the agent emits one line with the recommended tier only when it changes from the prior turn. Implementation: `caveman/tier-matrix.md` appended to `CLAUDE.md` + `AGENT_TIER_HINTS: bool` config flag. Expected savings: 50–70% blended reduction.

### Strategy 4 — Prompt Caching *(deferred — likely redundant with Claude Code defaults)*

Claude Code already caches the system prompt and `CLAUDE.md` automatically. Revisit if measurement on a real session shows the auto-cache is missing large doc files Claude reads every turn.
