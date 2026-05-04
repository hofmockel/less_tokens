# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

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
