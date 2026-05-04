# less_tokens — Vector Search for LLM Context Reduction

Drop-in vector search system that cuts agent token usage 5–10× by replacing full file `Read` with semantic search over pre-embedded chunks.

## What you get

1. **`tools/embeddings.py refresh`** — crawls source files, chunks them, embeds with local fastembed (`BAAI/bge-small-en-v1.5`, 384-dim), stores normalized float32 vectors in `index.db`.
2. **`tools/search.py "query"`** — embeds query, cosine-sims against stored vectors, returns top-k chunks (~600 tokens vs ~5K for a full file Read).
3. **`tools/embeddings.py health`** — verifies every expected source has ≥1 chunk; catches silent empty-index bugs.
4. **Two Claude Code hooks**:
   - `search-first.py` — PreToolUse gate: blocks `Read` on indexed files unless a search ran in the last 5 minutes.
   - `index-refresh.py` — PostToolUse: re-embeds in the background after `Edit`/`Write` on indexed files.

## Quickstart

```bash
# 1. Run the installer from your project root
python3 path/to/export_less_tokens/install.py

# 2. Edit tools/search_config.py (set VENV_PY, INDEXED_SOURCE_DIRS, etc.)

# 3. Build the initial index
<your-venv>/bin/python tools/embeddings.py refresh

# 4. Try it out
<your-venv>/bin/python tools/search.py "your query here"
```

The installer:
- Copies `tools/`, `schema/`, and `.claude/hooks/` into your project root
- Installs `fastembed` and `numpy` into the venv (if found)
- Initializes `index.db` from `schema/index.sql`
- Refuses to overwrite existing files (rerun with `--force` to overwrite)

## Configuration — only one file to edit

Everything project-specific lives in `tools/search_config.py`:

| Variable | Purpose |
|---|---|
| `VENV_PY` | Pass venv dir to `_venv_python()` (handles Win/macOS/Linux) |
| `EXCLUDED_DIR_NAMES` | Bare dir names to skip during indexing |
| `EXCLUDED_DIR_PREFIXES` | Path prefixes (with trailing `/`) to skip in hooks |
| `INDEXED_SOURCE_DIRS` | Subdirs whose `*.py` and `*.sql` files get indexed |
| `INDEXED_ROOT_GLOBS` | Root-level patterns (default `*.md`) |
| `SOURCE_TYPES` | `--source-type` CLI choices |

## Wiring into Claude Code

### CLAUDE.md — add this section

```markdown
## Search Before Read — MANDATORY

Before reading any indexed file in full, run `<venv>/bin/python tools/search.py "QUERY"`
first and use the returned chunks. Indexed sources: [list yours].

Use `Read` on indexed files only when:
1. `search.py` returned no relevant chunks, OR
2. you need to edit the file (Read is required by Edit), OR
3. `search.py` is unavailable (index empty, fastembed not installed).

A full Read of a large file is 5–10× more tokens than a search result. Default to search.
```

### `.claude/settings.local.json` — add hooks

```json
{
  "hooks": {
    "PreToolUse": [
      {"matcher": "Read",
       "hooks": [{"type": "command",
                  "command": "python3 .claude/hooks/search-first.py"}]}
    ],
    "PostToolUse": [
      {"matcher": "Edit|Write",
       "hooks": [{"type": "command",
                  "command": "python3 .claude/hooks/index-refresh.py"}]}
    ]
  }
}
```

### Optional: session-start integration

Add to your session-start preflight script:
```bash
<venv>/bin/python tools/embeddings.py refresh    # incremental, ~1s when no changes
<venv>/bin/python tools/embeddings.py health     # exits 1 on missing sources
```

## Cross-platform

- All paths use `pathlib.Path` — works on Windows/macOS/Linux.
- `_venv_python()` in `search_config.py` resolves to `Scripts/python.exe` on Windows, `bin/python` elsewhere.
- Hooks are pure Python — no bash-isms.

## Dependencies

- `fastembed` (~130MB model download to `~/.cache/huggingface` on first run)
- `numpy`
- Python 3.9+

## Files

```
export_less_tokens/
├── README.md                  # this file
├── install.py                 # cross-platform installer
├── tools/
│   ├── search_config.py       # ← edit this when porting
│   ├── embeddings.py          # build/refresh index
│   ├── search.py              # vector search CLI
│   └── db.py                  # sqlite helpers for index.db
├── schema/
│   └── index.sql              # documents table schema
└── hooks/
    ├── search-first.py        # PreToolUse gate
    └── index-refresh.py       # PostToolUse refresh
```

## Constraints (don't change)

- Model `BAAI/bge-small-en-v1.5` and `DIM = 384` must stay in sync between `embeddings.py` and `search.py`.
- Embeddings must be L2-normalized in storage; query also normalized → dot product == cosine similarity.
- `UNIQUE(source_path, source_key)` in schema is load-bearing for incremental refresh correctness.

## Adding custom source types

To index something beyond `*.md`/`*.py`/`*.sql` (e.g., CSV journals, JSON configs), add a custom enumerator at the end of `enumerate_sources()` in `embeddings.py`. Each entry is a 4-tuple: `(source_type, source_path, source_key, text)`. Add the type to `SOURCE_TYPES` in `search_config.py` if you want CLI filtering.
