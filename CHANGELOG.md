# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Changed
- **Installer targets the parent of the clone instead of `cwd`** — `install.py` now derives its target from `Path(__file__).resolve().parent.parent`, so cloning less_tokens into a host project (`cd ~/myproject && git clone ... less_tokens`) and running `python3 less_tokens/install.py` from anywhere always installs into `~/myproject`. This matches the documented "clone in, install up" workflow and makes `git pull && python3 install.py` from inside the clone a working upgrade path
- New `--target PATH` flag overrides the auto-derived target (useful for scratch projects, CI, testing); `--yes` bypasses the new suspicious-target sanity check that aborts if the auto-derived parent resolves to `/` or `$HOME` (catches a less_tokens clone that wasn't placed inside a project)

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
