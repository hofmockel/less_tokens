# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project purpose

This is a **toolkit** — it is installed *into other projects*, not run here directly. `install.py` copies `tools/`, `schema/`, `hooks/`, and `caveman/` into a target project and wires up Claude Code hooks. The four token-reduction strategies it deploys are: vector search (search before Read), caveman mode (terse output), tool output truncation, and session compaction.

## Commands

There is no formal test suite yet. Manual verification after changes:

```bash
# Install into a scratch project and verify end-to-end
python3 install.py --build    # from inside the scratch project root

# Build the local index (requires fastembed installed)
.venv/bin/python tools/embeddings.py refresh

# Search
.venv/bin/python tools/search.py "your query"
.venv/bin/python tools/search.py "query" --source-type code -k 5 --json

# Index health
.venv/bin/python tools/embeddings.py health
.venv/bin/python tools/db.py verify
```

## Architecture

### Layer split

The codebase has a clean two-layer split:

**Agent-agnostic core (`tools/`, `schema/`)**
- `tools/search_config.py` — the single config file users edit; all runtime constants live here including `VENV_PY`, `INDEXED_SOURCE_DIRS`, `STATE_DIR`, truncation limits, compaction threshold
- `tools/embeddings.py` — chunks source files by structure (Python AST, markdown headings, SQL statements), embeds with `BAAI/bge-small-en-v1.5` via `fastembed`, upserts into `index.db` with content-hash diffing
- `tools/search.py` — cosine similarity search over stored float32 vectors; writes `STATE_DIR/last-search` on every run so the search-first gate knows a search occurred
- `tools/db.py` — SQLite helpers; `connect_index()` opens `index.db` relative to the repo root
- `schema/index.sql` — `documents` table with `(source_path, source_key)` unique constraint; `embedding_model` column exists per row for planned multi-model support

**Claude Code hook layer (`hooks/`)**
- All hooks read a JSON payload from stdin and exit `0` (pass) or `2` (block/replace)
- `hooks/search-first.py` — PreToolUse on `Read`; blocks if the file is indexed and no search ran within `WINDOW_SECONDS` (300s hardcoded)
- `hooks/index-refresh.py` — PostToolUse on `Edit|Write`; fires `embeddings.py refresh` as a detached background process; logs to `.claude/state/index-refresh.log`
- `hooks/truncate-output.py` — PostToolUse on `Bash|Read|WebFetch`; caps output at `MAX_TOOL_OUTPUT_CHARS` (Bash uses head+tail lines strategy; others use 60/40 char split)
- `hooks/compact-trigger.py` — PostToolUse on `.*`; checks `transcript_path` size; has 25% hysteresis via `.claude/state/compact-trigger-last`
- `hooks/caveman-reminder.py` — PostToolUse on `.*`; nudges back to terse output if filler phrases detected

### State directory

`STATE_DIR` in `search_config.py` is `.claude/state/`.

### Chunking strategies

| File type | Strategy | Key unit |
|---|---|---|
| `.py` | `chunk_python` — AST parse | top-level `def`/`class`/`UPPER_CASE` |
| `.md` | `chunk_markdown` — regex H1/H2/H3 | heading sections |
| `CHANGELOG.md` | `chunk_changelog` — `## YYYY-MM-DD` headers | **Note:** Keep a Changelog format (`## [v] - date`) won't match; falls back to `chunk_markdown` (known bug) |
| `.sql` | `chunk_sql` — split on `;\n` | CREATE TABLE/VIEW/INDEX name | 

## Backlog and changelog lifecycle

When a backlog item ships, **both steps are required before the PR merges**:
1. Add an entry under `[Unreleased]` in `CHANGELOG.md` (user-perspective, Keep a Changelog format)
2. Delete the item from `BACKLOG.md` entirely — no strike-through, no "DONE" marker

The README reflects what the project *is today*; anything in both README and BACKLOG is a bookkeeping bug — remove the backlog entry.

## Known bugs worth avoiding

- `is_indexed()` logic differs between `hooks/search-first.py:74` and `hooks/index-refresh.py:37` — mid-path excluded dirs behave differently in each
- `search_config.py` default `INDEXED_SOURCE_DIRS` includes `"app/"` which the installer never creates — causes `health` to report gaps on fresh installs
- Vectors use native byte order (`tobytes()` / `frombuffer`); cross-endian `index.db` transfer silently corrupts scores
- `start_new_session=True` in `index-refresh.py:72` is a no-op on Windows; use `creationflags=subprocess.DETACHED_PROCESS` there
