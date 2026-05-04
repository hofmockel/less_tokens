# less_tokens — Vector Search for LLM Context Reduction

Drop-in system that cuts Claude agent token usage via two complementary strategies:

1. **Vector search** — replaces full-file `Read` with semantic search over pre-embedded chunks (5–10× fewer input tokens).
2. **Caveman mode** — instructs Claude to respond in terse, primitive prose (30–60% fewer output tokens).

---

## Prerequisites

- Python 3.9+
- A virtual environment already created for your project (`.venv`, `venv`, `env`, or `app/.venv`)
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed

---

## What you get

1. **`tools/embeddings.py refresh`** — crawls source files, chunks them, embeds with local fastembed (`BAAI/bge-small-en-v1.5`, 384-dim), stores normalized float32 vectors in `index.db`.
2. **`tools/search.py "query"`** — embeds query, cosine-sims against stored vectors, returns top-k chunks (~600 tokens vs ~5K for a full file Read).
3. **`tools/embeddings.py health`** — verifies every expected source has ≥1 chunk; catches silent empty-index bugs.
4. **Two Claude Code hooks**:
   - `search-first.py` — PreToolUse gate: blocks `Read` on indexed files unless a search ran in the last 5 minutes.
   - `index-refresh.py` — PostToolUse: re-embeds in the background after `Edit`/`Write` on indexed files.
5. **`caveman/caveman.md`** — CLAUDE.md snippet that enforces terse caveman-style output to cut response verbosity.

---

## Quickstart

```bash
# 1. Run the installer from your project root — use --skip-build until you configure search_config.py
#    macOS / Linux
python3 path/to/less_tokens_claude/install.py --skip-build

#    Windows
python path/to/less_tokens_claude/install.py --skip-build

# 2. Edit tools/search_config.py for your project layout
#    Set VENV_PY, INDEXED_SOURCE_DIRS, EXCLUDED_DIR_NAMES, etc.
#    (The installer prints the exact VENV_PY line to use.)

# 3. Build the initial index
#    macOS / Linux
.venv/bin/python tools/embeddings.py refresh

#    Windows
.venv\Scripts\python tools/embeddings.py refresh

# 4. Try it out
#    macOS / Linux
.venv/bin/python tools/search.py "your query here"

#    Windows
.venv\Scripts\python tools/search.py "your query here"
```

The installer:
- Copies `tools/`, `schema/`, `.claude/hooks/`, and `caveman/` into your project root
- Installs `fastembed` and `numpy` into the venv (if found)
- Initializes `index.db` from `schema/index.sql`
- Skips existing files (rerun with `--force` to overwrite)
- Prints the exact `VENV_PY` line to paste into `search_config.py`

---

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

**Example** — if your venv is at `.venv` and your source is in `src/`:
```python
VENV_PY = _venv_python(".venv")
INDEXED_SOURCE_DIRS = ("src/", "schema/")
```

---

## Wiring into Claude Code

### CLAUDE.md — add this section

```markdown
## Search Before Read — MANDATORY

Before reading any indexed file in full, run vector search first and use the
returned chunks. Replace `.venv/bin/python` with your actual venv python path.

    .venv/bin/python tools/search.py "QUERY"          # macOS/Linux
    .venv\Scripts\python tools/search.py "QUERY"       # Windows

Indexed sources: [list yours here].

Use `Read` on indexed files only when:
1. `search.py` returned no relevant chunks, OR
2. you need to edit the file (Read is required by Edit), OR
3. `search.py` is unavailable (index empty, fastembed not installed).

A full Read of a large file is 5–10× more tokens than a search result. Default to search.
```

### `.claude/settings.local.json` — add hooks

Replace `.venv/bin/python` with your actual venv python path. On Windows use `.venv\Scripts\python`.

```json
{
  "hooks": {
    "PreToolUse": [
      {"matcher": "Read",
       "hooks": [{"type": "command",
                  "command": ".venv/bin/python .claude/hooks/search-first.py"}]}
    ],
    "PostToolUse": [
      {"matcher": "Edit|Write",
       "hooks": [{"type": "command",
                  "command": ".venv/bin/python .claude/hooks/index-refresh.py"}]}
    ]
  }
}
```

### Optional: session-start preflight

```bash
# macOS / Linux
.venv/bin/python tools/embeddings.py refresh    # incremental, ~1s when no changes
.venv/bin/python tools/embeddings.py health     # exits 1 on missing sources

# Windows
.venv\Scripts\python tools/embeddings.py refresh
.venv\Scripts\python tools/embeddings.py health
```

---

## Strategy 2: Caveman Mode

Append `caveman/caveman.md` to your `CLAUDE.md` to cut response verbosity 30–60%.
Claude responds in terse, primitive prose — no filler, no apologies, no padding.
Code blocks are unaffected; only prose goes caveman.

```bash
cat caveman/caveman.md >> CLAUDE.md
```

To also wire the verbosity-nudge hook that fires if Claude slips back into verbose mode:

```json
{
  "hooks": {
    "PostToolUse": [
      {"matcher": ".*",
       "hooks": [{"type": "command",
                  "command": ".venv/bin/python .claude/hooks/caveman-reminder.py"}]}
    ]
  }
}
```

---

## Cross-platform

- All paths use `pathlib.Path` — works on Windows/macOS/Linux.
- `_venv_python()` in `search_config.py` resolves to `Scripts/python.exe` on Windows, `bin/python` elsewhere.
- Hooks are pure Python — no bash-isms.
- Hook commands in `settings.local.json` must use forward slashes on all platforms (JSON strings).

---

## Dependencies

- `fastembed` (~130MB model download to `~/.cache/huggingface` on first run)
- `numpy`
- Python 3.9+

---

## Files

```
less_tokens_claude/
├── README.md                  # this file
├── install.py                 # cross-platform installer
├── tools/
│   ├── search_config.py       # ← edit this when porting
│   ├── embeddings.py          # build/refresh index
│   ├── search.py              # vector search CLI
│   └── db.py                  # sqlite helpers for index.db
├── schema/
│   └── index.sql              # documents table schema
├── hooks/
│   ├── search-first.py        # PreToolUse gate
│   ├── index-refresh.py       # PostToolUse refresh
│   └── caveman-reminder.py    # PostToolUse verbosity nudge
└── caveman/
    └── caveman.md             # CLAUDE.md snippet for terse output
```

---

## Constraints (don't change)

- Model `BAAI/bge-small-en-v1.5` and `DIM = 384` must stay in sync between `embeddings.py` and `search.py`.
- Embeddings must be L2-normalized in storage; query also normalized → dot product == cosine similarity.
- `UNIQUE(source_path, source_key)` in schema is load-bearing for incremental refresh correctness.

---

## Adding custom source types

To index something beyond `*.md`/`*.py`/`*.sql` (e.g., CSV journals, JSON configs), add a custom enumerator at the end of `enumerate_sources()` in `embeddings.py`. Each entry is a 4-tuple: `(source_type, source_path, source_key, text)`. Add the type to `SOURCE_TYPES` in `search_config.py` if you want CLI filtering.
