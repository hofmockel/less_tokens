# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Output style — Caveman Mode

Talk like caveman. Short sentence. No filler word. No "certainly". No "I'd be happy to". No "Great question!". No padding. No summary at end.

Use noun. Use verb. Skip article when possible. Say what need saying. Stop.

Good: "File not found. Check path."
Bad: "I apologize, but I was unable to locate the file you specified. Could you please verify the path?"

Code blocks still normal — only prose go caveman.

## Search before Read

Index covers `tools/`, `tests/`, `schema/`, and root `*.md` files. Before reading any indexed file, run a search:

```bash
/search <query>
# or directly:
.claude/.venv-tokens/bin/python .claude/tools/search.py "<query>"
```

The `search-first` hook enforces this within the 300s gate window. Use `/build-index` to create or refresh the index.

## Project purpose

This is a **toolkit** — it is installed *into other projects*, not run here directly. less_tokens is cloned *into* a host project (e.g. `~/myproject/less_tokens/`) and `install.py` targets the parent directory (`~/myproject/`), deploying `tools/` → `.claude/tools/`, `schema/` → `.claude/schema/`, hooks → `.claude/hooks/`, venv → `.claude/.venv-tokens/`, and `index.db` → `.claude/index.db`. Re-running `install.py` after `git pull` upgrades the install in place. The four token-reduction strategies it deploys are: vector search (search before Read), caveman mode (terse output), tool output truncation, and session compaction.

## Commands

### Tests

```bash
# Unit + integration (no fastembed needed — matches CI)
pip install numpy pytest
pytest tests/unit/ -v
pytest tests/integration/ -v

# Single test
pytest tests/unit/test_chunkers.py -v
pytest tests/unit/test_chunkers.py::<test_name> -v

# Perf benchmarks (require fastembed; marker-gated, ubuntu-only in CI)
pip install fastembed numpy pytest
pytest tests/perf/ -v -m perf
```

pytest is configured in `pyproject.toml` (`testpaths=["tests"]`, `pythonpath=["."]`). CI
(`.github/workflows/tests.yml`) runs unit + integration on Python 3.9/3.11/3.12 × 3 OS.

### End-to-end verification

For hook behavior and the full install path, verify against a scratch project:

```bash
# Install into a scratch project. The installer targets the parent
# of this clone — cwd doesn't matter.
python3 install.py --build

# Override the target (e.g. when the scratch project lives elsewhere):
python3 install.py --target /path/to/scratch --yes --build

# Build the local index (requires fastembed installed)
.claude/.venv-tokens/bin/python .claude/tools/embeddings.py refresh

# Search
.claude/.venv-tokens/bin/python .claude/tools/search.py "your query"
.claude/.venv-tokens/bin/python .claude/tools/search.py "query" --source-type code -k 5 --json

# Index health
.claude/.venv-tokens/bin/python .claude/tools/embeddings.py health
.claude/.venv-tokens/bin/python .claude/tools/db.py verify
```

## Architecture

### Layer split

The codebase has a clean two-layer split:

**Agent-agnostic core (deployed to `.claude/tools/` and `.claude/schema/`)**
- `tools/search_config.py` → `.claude/tools/search_config.py` — the single config file users edit; all runtime constants live here including `VENV_PY`, `INDEXED_SOURCE_DIRS`, `STATE_DIR`, truncation limits, compaction threshold
- `tools/embeddings.py` → `.claude/tools/embeddings.py` — chunks source files by structure (Python AST, markdown headings, SQL statements), embeds with `BAAI/bge-small-en-v1.5` via `fastembed`, upserts into `.claude/index.db` with content-hash diffing
- `tools/search.py` → `.claude/tools/search.py` — cosine similarity search over stored float32 vectors; writes `STATE_DIR/last-search` on every run so the search-first gate knows a search occurred
- `tools/db.py` → `.claude/tools/db.py` — SQLite helpers; `connect_index()` opens `.claude/index.db`
- `schema/index.sql` → `.claude/schema/index.sql` — `documents` table with `(source_path, source_key)` unique constraint; `embedding_model` column exists per row for planned multi-model support

**Claude Code hook layer (`hooks/`)**
- All hooks read a JSON payload from stdin and exit `0` (pass) or `2` (block/replace)
- `hooks/search-first.py` — PreToolUse on `Read`; blocks if the file is indexed and no search ran within `WINDOW_SECONDS` (300s hardcoded)
- `hooks/index-refresh.py` — PostToolUse on `Edit|Write`; fires `embeddings.py refresh` as a detached background process; logs to `.claude/state/index-refresh.log`
- `hooks/truncate-output.py` — PostToolUse on `Bash|Read|WebFetch`; caps output at `MAX_TOOL_OUTPUT_CHARS` (Bash uses head+tail lines strategy; others use 60/40 char split)
- `hooks/compact-trigger.py` — PostToolUse on `.*`; checks `transcript_path` size; has 25% hysteresis via `.claude/state/compact-trigger-last`
- `hooks/caveman-reminder.py` — PostToolUse on `.*`; nudges back to terse output if filler phrases detected

Hooks are unit-tested by importing them as modules via `tests/conftest.py:load_hook()` (it puts `tools/` on `sys.path` so the source tools are importable during tests, then execs the hook file). Keep hook logic importable — no side effects at module load.

### State directory

`STATE_DIR` in `search_config.py` is `CLAUDE_DIR / "state"` (i.e., `.claude/state/` in the host project).

### Chunking strategies

| File type | Strategy | Key unit |
|---|---|---|
| `.py` | `chunk_python` — AST parse | top-level `def`/`class`/`UPPER_CASE` |
| `.md` | `chunk_markdown` — regex H1/H2/H3 | heading sections |
| `CHANGELOG.md` | `chunk_changelog` — `## YYYY-MM-DD` headers | **Note:** Keep a Changelog format (`## [v] - date`) won't match; falls back to `chunk_markdown` (known bug) |
| `.sql` | `chunk_sql` — split on `;\n` | CREATE TABLE/VIEW/INDEX name | 

## Backlog and changelog lifecycle

The maintainer is responsible for both steps before merging any fix PR:
1. Add an entry under `[Unreleased]` in `CHANGELOG.md` (user-perspective, Keep a Changelog format)
2. Delete the item from `BACKLOG.md` entirely — no strike-through, no "DONE" marker

The README reflects what the project *is today*; anything in both README and BACKLOG is a bookkeeping bug — remove the backlog entry.

## Known bugs worth avoiding

- `is_indexed()` logic differs between `hooks/search-first.py:74` and `hooks/index-refresh.py:37` — mid-path excluded dirs behave differently in each

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
