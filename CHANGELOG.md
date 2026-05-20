# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- **`embeddings.py switch-model`** — atomically rewrites `EMBEDDING_MODEL` + `EMBEDDING_DIM` in `search_config.py` and runs `refresh --full`, preventing the silent dimension mismatch that occurs when the model is changed by hand but the dim isn't (scores quietly become wrong against the existing index). Refuses a no-op (same model + same dim) so a misclick doesn't trigger a gratuitous full re-index. Usage: `python3 tools/embeddings.py switch-model BAAI/bge-base-en-v1.5 --dim 768`
- **`.pre-commit-config.yaml`** — opt-in pre-commit wiring for `ruff` (lint + format). Contributors run `pip install pre-commit && pre-commit install` once and get the same lint feedback locally that CI enforces. Pyright is omitted for now (not part of the test toolchain)
- **Optional module-docstring context in code chunks** — new `CHUNK_INCLUDE_MODULE_CONTEXT` flag in `search_config.py` (default `False`); when enabled, `chunk_python` prefixes each top-level def/class chunk with the file's module docstring (as a comment) so a single search hit conveys the file's purpose without a follow-up Read. Opt-in because it changes content hashes and re-embeds all Python sources on the next refresh
- **`embeddings.py stats --verbose`** — extends `stats` with a dashboard: indexed-file count, index age (derived from the newest chunk's `updated_at`), and coverage vs expected sources (`covered/expected` + percent, with up to 10 missing paths listed). Plain `stats` output is unchanged
- **`search.py` query history log** — every run appends one best-effort JSONL record (UTC timestamp, query, top result score, result count) to `.claude/state/search-history.log`, so maintainers can audit what Claude searched for and spot queries that consistently return weak results. Logging failures are swallowed — the audit log never breaks the search it records
- **`embeddings.py refresh --dry-run`** — preview a refresh without writing: prints `add` / `update` / `unchanged` / `delete` chunk counts (and treats every existing row as a delete under `--full`). Loads no embedding model and leaves `index.db` untouched, so it works even when fastembed isn't installed
- **Stale-index warning in `search.py`** — before results, `search.py` compares the newest indexed source-file mtime against `index.db` and prints a one-line `WARN: index may be stale … run tools/embeddings.py refresh` to stderr when a source is newer (the auto-refresh hook can lag or fail). Stderr only — stdout/JSON output is unchanged
- **`search.py --min-score`** — drop top-k results whose cosine score is below a floor (e.g. `--min-score 0.5`), so Claude doesn't act on semantically unrelated chunks that merely rank in the top-k. `search()` also takes a `min_score` kwarg; unset (default) keeps current behavior
- **Install E2E workflow** (`.github/workflows/install-e2e.yml`) — subprocess-level test of `install.py` across Ubuntu / macOS / Windows. Covers fresh install (cwd-independent target resolution), idempotent re-run from inside the clone, `--target` override, suspicious-target sanity-check abort, and source-self guard. Complements the function-level coverage in `tests/integration/test_install.py`, which the existing Tests workflow runs
- **`patch_venv_py` tests** in `tests/integration/test_install.py` — six cases covering the default-value patch, idempotent re-run, user-customization preservation, missing-`VENV_PY` no-op, absolute-path fallback when the venv lives outside `target_root`, and preservation of surrounding lines/comments
- **`install.py --dry-run`** — preview the full blast radius before mutating the host project: resolved target, every file that would be copied (new/skip/overwrite), venv detection result, `search_config.py` variables that would be injected, and the `.claude/settings.json` hooks that would be wired — all without writing anything
- **`install.py --uninstall`** (with `--purge-index`) — reverse a deployment: strip the less_tokens hook entries from `.claude/settings.json`, remove the copied `tools/`, `schema/`, and `.claude/hooks/` files, and with `--purge-index` also drop `index.db` and its WAL sidecars — while leaving host-authored files and `tools/search_config.py` untouched
- **`install.py --gitignore`** — add a managed `.gitignore` block for generated artifacts (`index.db`, `.claude/state/`) so they don't pollute the host repo; a one-time tip points to the flag when the block is absent
- **Namespace-collision guard (`--allow-merge`)** — the installer now detects pre-existing non-less_tokens files in the host's `tools/` or `schema/` and aborts before any write; `--allow-merge` opts into merging anyway
- **`INDEXED_DOC_GLOBS` config var** — index markdown that lives outside the repo root (e.g. `docs/*.md`, or a vendored subproject's docs) alongside `INDEXED_ROOT_GLOBS`. Defaults to empty, so existing installs are unaffected; entries are keyed by full path relative to the repo so same-named files at different depths stay distinct

### Changed
- **`install.py` builds the index by default** — a default install now runs `embeddings.py refresh` (and the post-build smoke check) so a single command leaves the project ready to search. Adds ~30s and a ~130 MB model download on first run; `--no-build` opts out and prints the manual build commands in NEXT STEPS (replaces the old opt-in `--build`)
- **Managed `.gitignore` block is now default-on** — `install.py` adds the `index.db` / `.claude/state/` ignore block by default in any git target; opt out with `--no-gitignore` (replaces the old opt-in `--gitignore`). Removes the silent `git status` pollution after a fresh install
- **`install.py --build` runs a post-build smoke check** — after a successful `embeddings.py refresh`, the installer now invokes `embeddings.py stats` and exits non-zero if it fails, so a broken or empty index is caught at install time rather than on the user's first search. `stats` (not `health`) is used to avoid false alarms on host repos whose `INDEXED_SOURCE_DIRS` haven't been customized yet
- **Installer NEXT STEPS announces search-first activation** — `install.py` now prints a final note explaining that the PreToolUse hook is live for any already-running Claude session in the target, will block Reads on indexed files until a search runs, and points at `WINDOW_SECONDS` in `search_config.py` for tuning. Removes the "why is Read suddenly erroring?" debugging trip after a fresh install
- **`WINDOW_SECONDS` is now configurable** — the search-first hook's gate window (default 300s) lives in `search_config.py` instead of being hardcoded in `hooks/search-first.py`. Tune the aggressiveness of the search-before-Read gate without editing hook source
- **Venv detection prefers `$VIRTUAL_ENV`** — `install.detect_venv()` and `search_config._venv_python()` now check the `VIRTUAL_ENV` env var first (set by `activate`, reliable on all platforms) before the relative-path guesses. An activated venv is auto-used without editing `search_config.py` or passing `--venv`; falls back to the previous behavior when unset or stale
- **`search.py` deduplicates results by file** — when multiple top-k chunks come from the same `source_path`, only the best-scoring chunk is kept and the freed slot is filled with the next distinct file, so `k` results cover `k` files instead of near-duplicate chunks of one. `--min-score` still applies
- **Embedding model + dimension are now configurable** — `EMBEDDING_MODEL` / `EMBEDDING_DIM` live in `search_config.py` instead of being hardcoded in `embeddings.py`, so users can switch embedding models without editing tool source. `embeddings.py` re-exports them as `MODEL` / `DIM` and `search.py` reads `DIM` via that re-export, so the value is config-sourced end to end (change both together and re-run `embeddings.py refresh --full`)
- **Installer auto-patches `VENV_PY`** — after detecting the venv, `install.py` rewrites `VENV_PY = _venv_python("...")` in `tools/search_config.py` to the detected venv (relative to the host project when possible). Conservative match: only fires when the existing value is still the source default, so user customizations are preserved. NEXT STEPS output now skips the manual VENV_PY instruction when the auto-patch lands, leaving only `INDEXED_SOURCE_DIRS` as project-specific configuration the user must edit
- **Installer targets the parent of the clone instead of `cwd`** — `install.py` now derives its target from `Path(__file__).resolve().parent.parent`, so cloning less_tokens into a host project (`cd ~/myproject && git clone ... less_tokens`) and running `python3 less_tokens/install.py` from anywhere always installs into `~/myproject`. This matches the documented "clone in, install up" workflow and makes `git pull && python3 install.py` from inside the clone a working upgrade path
- New `--target PATH` flag overrides the auto-derived target (useful for scratch projects, CI, testing); `--yes` bypasses the new suspicious-target sanity check that aborts if the auto-derived parent resolves to `/` or `$HOME` (catches a less_tokens clone that wasn't placed inside a project)
- **Benign urllib3 LibreSSL warning is suppressed** — on macOS system Python (LibreSSL), importing `fastembed` made every `search.py` run print a `urllib3 NotOpenSSLWarning` to stderr before results, polluting hook output and any captured search results. `embeddings.py` now installs a process-wide filter for that known message at import; `search.py` imports `embeddings` at module load, so both entrypoints are quiet

### Fixed
- **`search-first.py` docstring now names the correct settings file** — it said `install.py` wires the hook into `.claude/settings.local.json`, but the installer deliberately writes the project-shared `.claude/settings.json` (so Claude rewrites can't clobber the hooks block). The stale docstring misled anyone debugging why the gate wasn't firing
- **The search-first gate no longer blocks Reads of `.md` files it can never clear** — `is_indexed()` (in both `hooks/search-first.py` and `hooks/index-refresh.py`) treated any `.md` under an `INDEXED_SOURCE_DIRS` entry as indexed, but `enumerate_sources()` only collects `*.py` / `*.sql` from those dirs — never `*.md`. Adding a directory to `INDEXED_SOURCE_DIRS` therefore made the gate block Reads of `.md` files absent from `index.db`, with no scoped search able to clear it. The `INDEXED_SOURCE_DIRS` branch now matches only `.py` / `.sql`, so the gate reflects what is actually indexed (root and doc-glob markdown are unaffected)
- **Repeated markdown headings no longer silently drop a chunk when a literal `## Foo_2` also exists** — `chunk_markdown` deduped a repeated `## Foo` to source key `Foo_2`, which collided with a literal `## Foo_2` heading in the same file; the two chunks shared `(source_path, source_key)` and the index UPSERT silently kept only one, so a whole section became unsearchable. Dedup suffixes are now chosen to skip any key that already exists literally in the file (or was already emitted), so every chunk keeps a unique key
- **A single permission-denied directory no longer aborts the whole index refresh** — `embeddings.py refresh` walked each `INDEXED_SOURCE_DIRS` entry with `rglob`, which raised `PermissionError` and killed the entire run (leaving `index.db` stale) the moment it hit one unreadable subtree, even when every other source was readable. Unreadable directories are now skipped with a `WARN` and the remaining sources are still indexed
- **A single permission-denied directory no longer crashes `embeddings.py health` / `db.py verify`** — `expected_source_paths()`, the coverage check behind `health` and `verify`, had the same `rglob` flaw as the refresh path: one unreadable subtree raised `PermissionError` and crashed the whole report instead of listing coverage, even when every other source was readable. Unreadable directories are now skipped with a `WARN` and the remaining sources are still reported
- **A transiently-unreadable source directory no longer silently deletes its indexed rows** — once `refresh` learned to skip an unreadable subtree and continue, it received a *partial* source list, and its prune step deleted every index row not present in that partial list (`refresh --full` wiped the table outright), so a temporarily-locked directory lost its still-usable search entries until a full rebuild. `refresh` now detects an incomplete enumeration, skips both delete paths with a `WARN`, and keeps the existing rows until a clean refresh reconciles them
- **Embedding vectors are stored little-endian so `index.db` is portable across CPU endianness** — the writer serialized vectors with the host's native byte order and the reader decoded them the same way, so an `index.db` built on a little-endian machine and read on a big-endian one (s390x, some POWER/ARM) returned silently wrong cosine similarity scores with no error. Serialization is now pinned to little-endian `<f4` at a single shared point used by both the indexer and the search reader
- **Pre-fix indexes are auto-invalidated on upgrade so old vectors aren't misread** — bumping the little-endian fix above without re-indexing would leave content-hash-unchanged rows in their old native byte order while the reader now always decodes `<f4` (a v1 index built on a big-endian host would score silently wrong). The `index.db` schema is now **v2**: `db.py migrate` drops the `documents` rows when crossing the v1→v2 boundary, and `embeddings.py refresh` calls a new `ensure_current_schema()` at startup so this one-time invalidation runs automatically on the normal upgrade path (`install --build`, a manual `refresh`, or the index-refresh hook) — no manual `db.py migrate` needed. Note: byte order was not recorded in v1, so the first refresh after upgrading performs a one-time full re-embed for **all** users (≈30 s plus model download if not cached), not only big-endian ones
- **An `index.db` built before the little-endian pin is auto-rebuilt instead of returning silently corrupt scores** — pinning vectors little-endian did not fix indexes already written on a big-endian host: `refresh` only re-embeds a row when its source *text* changes, so the old native-endian blobs survived and `search` decoded them little-endian — wrong cosine scores with no error until a manual full rebuild. `refresh` now records a vector-layout marker in the database (`PRAGMA user_version`); an index that predates the marker is fully re-embedded once and then stamped, so the next routine refresh self-heals it. The forced rebuild is deferred when a source directory is unreadable, so it never deletes rows it cannot re-embed
- **`search.py --source-type` choices now track the index instead of a static list** — `--source-type` was validated against a hardcoded `SOURCE_TYPES` that had drifted from `documents.source_type`: it advertised values the indexer never produces (`journal`, `note` → always zero results) and rejected values a different or older index legitimately contained. Choices are now derived from `SELECT DISTINCT source_type FROM documents` at runtime, and left unconstrained when the index is unavailable
- **Venv paths containing a quote or backslash no longer write an invalid `search_config.py`** — `install.py` interpolated the detected venv path straight into the `VENV_PY = _venv_python("…")` line it writes (and the next-steps hint it prints), so a path with an embedded `"` produced a `SyntaxError` in the host config (and an un-pasteable hint). Both sites now emit a JSON-escaped string literal via a shared `_venv_python_call()` helper — byte-identical to the previous form for ordinary paths
- **`index-refresh.py` now detaches the background refresh on Windows** — `subprocess.Popen(..., start_new_session=True)` is POSIX-only and was silently ignored on Windows, leaving the `embeddings.py refresh` child attached to the Claude Code process; the hook now branches on `sys.platform`, passing `creationflags=DETACHED_PROCESS|CREATE_NEW_PROCESS_GROUP` on Windows and keeping `start_new_session=True` on POSIX
- `tests/integration/test_install.py` updated for the new `target_root` parameter on `copy_tree` / `handle_search_config`; tests no longer monkeypatch a now-removed module-level `TARGET_ROOT`
- **Installer no longer leaves a silent half-install on abort** — the venv is resolved/validated and the namespace-collision check now runs *before* any files are copied, so a missing venv or other failed precondition aborts with nothing written, instead of copying hooks that were never registered with Claude Code and leaving the toolkit silently inert
- **Markdown indexed by relative path, not bare filename** — `enumerate_sources` keyed root markdown by `f.name`, so two same-named `.md` files reachable from the index (e.g. a root `CLAUDE.md` and one under a vendored subdir) collided on `(source_path, source_key)` and the UPSERT silently dropped one. Markdown is now keyed by path relative to the repo root; root entries are unchanged (`CLAUDE.md` stays `CLAUDE.md`)

### Added
- **Token savings tracking** — new `tools/savings_log.py` + `tools/stats.py`; disabled by default (`TRACK_SAVINGS = False` in `search_config.py`); enable with `python tools/stats.py --enable` (or the interactive prompt); hooks log chars saved per strategy to `.claude/state/savings.jsonl`; `--report` writes a markdown summary to `.claude/state/savings-report.md`; `--all` shows all-time totals; `--disable` turns tracking off; `embeddings.py savings` dispatches to the same interface
- `TRACK_SAVINGS` config variable in `tools/search_config.py`
- **Stats GitHub Actions workflow** (`.github/workflows/stats.yml`) — runs stats unit tests on Python 3.9 / 3.11 / 3.12 × all three OS, plus a separate job that enables tracking, logs synthetic events, generates a savings report, uploads it as a workflow artifact, and resets tracking to off
- Unit tests for `savings_log` and `stats` in `tests/unit/test_stats.py` (append guard, timestamp injection, record filtering, summarize aggregation, table rendering, report generation, config patching)

### Fixed
- `is_indexed()` in `hooks/index-refresh.py` now uses the same mid-path exclusion check as `search-first.py` (`("/" + d) in ("/" + rel)`), so both hooks agree on files inside excluded directories that appear at non-root path positions
- `chunk_sql` no longer splits SQL statements on semicolons that appear inside `--` line comments; comments are stripped before splitting so statement boundaries are found correctly
- Removed `"app/"` from the default `INDEXED_SOURCE_DIRS` in `tools/search_config.py` — the installer never creates that directory, so fresh installs no longer report a health gap for every file under `app/`
- `chunk_changelog` now recognises Keep-a-Changelog headers (`## [version] - date`, `## [Unreleased]`) in addition to date-only headers (`## YYYY-MM-DD`); previously any CHANGELOG using the standard format fell back to `chunk_markdown` and lost per-version chunk structure

### Added
- **`.claudeignore`** — ships with the toolkit to exclude documentation (`README.md`, `documentation.md`, `CHANGELOG.md`), CI config (`.github/`), bug-hunt files (`bughunt/`), benchmark artifacts (`tests/perf/latest.json`), and target-project templates (`caveman/caveman.md`) from Claude's project file scope; reduces noise in file suggestions and directory listings during code work
- **Test suite and CI** — `tests/unit/` covers chunkers, db, hook protocol, `is_indexed` parity, config merge, and settings wiring; `tests/integration/test_install.py` runs end-to-end installer scenarios; `tests/perf/test_bench_tokens.py` benchmarks token-reduction per strategy; GitHub Actions matrix runs unit and integration tests on Python 3.9 / 3.11 / 3.12 × Ubuntu / macOS / Windows, perf benchmarks on Ubuntu with fastembed model caching and artifact upload
- **Non-destructive installer** — `install.py` now handles re-runs and upgrades safely:
  - `search_config.py` is never overwritten wholesale; only variables absent in the existing file are injected, preserving all user-set values
  - `copy_tree` detects locally-modified files and shows a `+N -M lines` diff summary instead of silently overwriting; `--overwrite-modified` is required to update them
  - `.claude/settings.local.json` hook wiring is now automatic and idempotent — the installer merges entries by `(event_type, matcher, command)` identity so re-running never duplicates hook entries
  - `--caveman` next-steps hint checks whether the caveman section heading already exists in `CLAUDE.md` and prints "already present" instead of repeating the append instruction
  - Granular force flags: `--force-hooks`, `--force-tools`, `--force-config` (each scoped to one directory); `--force` remains a shorthand for all three
- `tools/db.py init` now records schema version in the `schema_version` table on first run
- `tools/db.py migrate` subcommand applies pending schema migrations and updates the recorded version

### Added
- **Tool output truncation (Strategy 3)** — new `hooks/truncate-output.py` PostToolUse hook caps oversized Bash, Read, and WebFetch results to a configurable character ceiling (default 4000 ≈ 1000 tokens), saving 40–80% of tool-output tokens on verbose commands like `git log`, test runners, and large file reads
- Bash output uses head+tail truncation (preserves first 50 + last 20 lines so command start and trailing errors both survive); Read/WebFetch use a 60/40 character split
- Three new config variables in `tools/search_config.py`: `MAX_TOOL_OUTPUT_CHARS`, `TOOL_OUTPUT_HEAD_LINES`, `TOOL_OUTPUT_TAIL_LINES` (set `MAX_TOOL_OUTPUT_CHARS = 0` to disable without unwiring the hook)
- `--truncate` flag to `install.py` to print the truncation hook's `settings.local.json` wiring in the next-steps output
- **Conversation compaction trigger (Strategy 5)** — new `hooks/compact-trigger.py` PostToolUse hook reads the session transcript path from the hook payload, gates on `MAX_SESSION_CHARS` (default 500 KB ≈ 125k tokens), and nudges Claude to run `/compact` when the threshold is crossed; saves 50–70% of input tokens on long sessions
- Hysteresis state at `.claude/state/compact-trigger-last` ensures the reminder only re-fires after the transcript grows another 25%, so it won't spam every subsequent tool call once tripped
- New config variable `MAX_SESSION_CHARS` in `tools/search_config.py` (set to 0 to disable)
- `--compact` flag to `install.py` to print the compaction trigger's `settings.local.json` wiring in the next-steps output
- **Cline adapter (`adapters/cline/`)** — first non-Claude-Code agent integration. Ships a FastMCP stdio server (`mcp-search/server.py`) that exposes the project's vector search as an MCP `search` tool Cline can call natively, plus `.clinerules/` instruction files (`01-search-before-read.md`, `02-caveman.md`) that port Strategies 1 and 2 to Cline's project-rules format
- `adapters/cline/install-cline.py` — adapter installer: copies `.clinerules/`, patches `STATE_DIR` to `.less_tokens/state/`, installs the `mcp` SDK into the project venv, prints the OS-specific `cline_mcp_settings.json` snippet for user-level MCP registration
- New `STATE_DIR` config variable in `tools/search_config.py` (default `.claude/state/`) so non-Claude-Code adapters can override it without leaving a stray `.claude/` directory in unrelated projects
- `.gitignore` now ignores `.venv/`, `venv/`, `env/`, `app/.venv/` so contributors can't accidentally commit a virtual environment

### Changed
- `tools/search.py` and `hooks/search-first.py` now read the search-first state file path from `STATE_DIR` in `search_config.py` instead of hardcoding `.claude/state/`
- `tools/db.py` and `tools/search.py` now pass `encoding="utf-8"` explicitly on text IO so non-ASCII content survives Windows hosts (default cp1252)
- `hooks/caveman-reminder.py` verbosity patterns also catch `Certainly.`, `Absolutely.`, and `Of course.` (period endings, the most common shape) — previously only matched `,` and `!`
- `tools/embeddings.py` uses `datetime.now(timezone.utc)` instead of the deprecated `datetime.utcnow()` (Python 3.12+ DeprecationWarning)
- `hooks/index-refresh.py` drops the redundant `VENV_PY as _VENV_PY` import alias

### Fixed
- `tools/search.py` now catches `sqlite3.OperationalError` and returns an empty result with a stderr advisory when `index.db` is missing or uninitialised (previously crashed)
- `hooks/search-first.py` `search_was_recent()` no longer races between `exists()` and `stat()`; `FileNotFoundError` is handled instead of crashing the gate
- `README.md` quickstart removed the `--skip-build` flag that was deleted from `install.py` in 0.2.0 (the default behaviour is already to skip the build; `--build` is the opt-in)
- `hooks/search-first.py` docstring example replaced `python3` with the venv-python placeholder so Windows users aren't pointed at a non-existent command
- `schema/index.sql` `embedding` column comment corrected from `float32[1024], voyage-3-lite output` to reflect the actual model and 384-dim output
- `tools/search.py` removed a stale comment referencing a non-existent `voyage_embed` function

## [0.2.0] - 2026-05-03

### Added
- **Caveman mode** — new `caveman/caveman.md` CLAUDE.md snippet that instructs Claude to respond in terse, primitive prose, reducing output tokens 30–60%
- `hooks/caveman-reminder.py` — PostToolUse hook that detects verbose filler patterns ("Certainly!", "I apologize", "I'd be happy to", etc.) and nudges Claude back to caveman style
- `--caveman` flag to `install.py` to copy caveman assets during install
- `--build` flag to `install.py` to opt into building the index immediately after install
- Prerequisites section in README (Python 3.9+, venv, Claude Code)
- Badges in README (Python version, platform, Claude Code)
- Table of contents in README
- Contributing and License sections in README

### Changed
- `--skip-build` is now the default in `install.py` — prevents a wasted index build before `search_config.py` is configured
- `install.py` next-steps output now prints the exact `VENV_PY = _venv_python("...")` line to paste into `search_config.py`
- `install.py` next-steps output now prints the resolved venv python path for use in hook commands
- `hooks/search-first.py` gate message now uses `VENV_PY` from `search_config` instead of a hardcoded Unix path
- README restructured to professional standard: table of contents, installation flag table, configuration variable table, concrete usage examples, before/after token comparison
- README hook commands changed from `python3 .claude/hooks/...` to venv-python path (fixes Windows compatibility)
- README venv path examples now show both macOS/Linux (`bin/python`) and Windows (`Scripts\python`) variants
- README file tree corrected from `export_less_tokens/` to `less_tokens_claude/`

### Fixed
- `tools/search_config.py` docstring referenced a non-existent `less_tokens.md` file

## [0.1.0] - 2026-05-03

### Added
- `tools/embeddings.py` — crawls source files, chunks by structure (functions, headings, SQL statements), embeds with `BAAI/bge-small-en-v1.5` (384-dim), stores L2-normalized float32 vectors in SQLite
- `tools/search.py` — semantic search CLI; embeds query, computes cosine similarity, returns top-k chunks
- `tools/db.py` — SQLite helpers; WAL mode, schema init, row-count verification
- `tools/search_config.py` — single config file for venv path, indexed dirs, exclusions, and source types
- `schema/index.sql` — `documents` table with `UNIQUE(source_path, source_key)` constraint for incremental refresh
- `hooks/search-first.py` — PreToolUse hook that blocks `Read` on indexed files unless a search ran in the last 5 minutes
- `hooks/index-refresh.py` — PostToolUse hook that re-embeds in the background after `Edit`/`Write` on indexed files
- `install.py` — cross-platform installer (Windows/macOS/Linux); auto-detects venv, installs deps, initializes DB
- `.gitignore` — ignores `index.db`, `__pycache__/`, `*.pyc`, `*.pyo`, `.claude/state/`, `.DS_Store`

[Unreleased]: https://github.com/hofmockel/less_tokens_claude/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/hofmockel/less_tokens_claude/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/hofmockel/less_tokens_claude/releases/tag/v0.1.0
