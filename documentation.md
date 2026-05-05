# Documentation

Full reference for installing, configuring, and using `less_tokens`.

---

## Prerequisites

- Python 3.9+
- A virtual environment for your project (`.venv`, `venv`, `env`, or `app/.venv`)
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed

---

## Installation

Run the installer from your **project root** — the directory where you want the tools deployed.

```bash
# macOS / Linux
python3 path/to/less_tokens_claude/install.py

# Windows
python path/to/less_tokens_claude/install.py
```

> By default the installer skips the index build so you can configure `search_config.py` first. Pass `--build` to build immediately (step 3 below covers manual build).

The installer copies `tools/`, `schema/`, `.claude/hooks/`, and `caveman/` into your project, installs `fastembed` and `numpy`, and initializes `index.db`.

**Optional flags:**

| Flag | Effect |
|---|---|
| `--force` | Overwrite existing files |
| `--venv PATH` | Point to a venv not in a standard location |
| `--skip-deps` | Skip `pip install` (dependencies already installed) |
| `--build` | Build the index immediately after install |
| `--caveman` | Also copy `caveman/` for terse output mode |
| `--truncate` | Print next-steps wiring for the tool output truncation hook |
| `--compact` | Print next-steps wiring for the conversation compaction trigger hook |

---

## Configuration

**Edit one file:** `tools/search_config.py`

The installer prints the exact line to paste in. At minimum, set your venv path and the source directories to index:

```python
# tools/search_config.py

VENV_PY = _venv_python(".venv")               # change to your venv location
INDEXED_SOURCE_DIRS = ("src/", "schema/")      # dirs whose .py and .sql files get indexed
```

All variables:

| Variable | Purpose |
|---|---|
| `VENV_PY` | Venv python path (handles Win/macOS/Linux automatically) |
| `INDEXED_SOURCE_DIRS` | Subdirs to index for `.py` and `.sql` files |
| `INDEXED_ROOT_GLOBS` | Root-level patterns to index (default: `*.md`) |
| `EXCLUDED_DIR_NAMES` | Directory names to skip (e.g. `node_modules`) |
| `EXCLUDED_DIR_PREFIXES` | Path prefixes to skip (e.g. `legacy/`) |
| `SOURCE_TYPES` | Labels for `--source-type` CLI filtering |
| `MAX_TOOL_OUTPUT_CHARS` | Truncation ceiling for Bash/Read/WebFetch results (set 0 to disable) |
| `TOOL_OUTPUT_HEAD_LINES` | Bash head lines kept on truncation |
| `TOOL_OUTPUT_TAIL_LINES` | Bash tail lines kept on truncation (errors live here) |
| `MAX_SESSION_CHARS` | Session transcript size that triggers a `/compact` reminder (set 0 to disable) |
| `STATE_DIR` | Where the search-first state file lives (default `.claude/state/`) |

---

## Usage

### Build the index

Run this once after configuring, and again whenever you want a full refresh:

```bash
# macOS / Linux
.venv/bin/python tools/embeddings.py refresh

# Windows
.venv\Scripts\python tools/embeddings.py refresh
```

> First run downloads the embedding model (~130 MB to `~/.cache/huggingface`). Subsequent runs are incremental and typically take under a second.

### Search

```bash
# macOS / Linux
.venv/bin/python tools/search.py "your query"

# Windows
.venv\Scripts\python tools/search.py "your query"
```

**Examples:**

```bash
.venv/bin/python tools/search.py "how are imports validated"
.venv/bin/python tools/search.py "cash floor logic" --source-type code
.venv/bin/python tools/search.py "deployment steps" -k 5 --json
```

### Verify the index

```bash
.venv/bin/python tools/embeddings.py health   # exits 1 if any source has no chunks
.venv/bin/python tools/db.py verify           # prints row counts per source type
```

### Caveman mode

Append the caveman snippet to your `CLAUDE.md` to enforce terse output:

```bash
cat caveman/caveman.md >> CLAUDE.md
```

Before and after example:

> **Before:** "I apologize, but I was unable to locate the file you specified. Could you please verify the path and try again?"
>
> **After:** "File not found. Check path."

---

## Wiring into Claude Code

### 1. Add to CLAUDE.md

```markdown
## Search Before Read — MANDATORY

Before reading any indexed file in full, run vector search first:

    .venv/bin/python tools/search.py "QUERY"     # macOS/Linux
    .venv\Scripts\python tools/search.py "QUERY"  # Windows

Indexed sources: [list your dirs here]

Use `Read` directly only when search returns no relevant chunks,
when you need to edit a file, or when the index is unavailable.
```

### 2. Add hooks to `.claude/settings.local.json`

Replace `.venv/bin/python` with your actual venv python path (printed by the installer). On Windows use `.venv\Scripts\python`.

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Read",
        "hooks": [{"type": "command", "command": ".venv/bin/python .claude/hooks/search-first.py"}]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [{"type": "command", "command": ".venv/bin/python .claude/hooks/index-refresh.py"}]
      }
    ]
  }
}
```

**Optional — caveman nudge hook** (fires if Claude uses verbose filler):

```json
{
  "matcher": ".*",
  "hooks": [{"type": "command", "command": ".venv/bin/python .claude/hooks/caveman-reminder.py"}]
}
```

**Optional — tool output truncation hook** (caps oversized Bash/Read/WebFetch results). Add as another `PostToolUse` entry, **before** the caveman entry if both are present:

```json
{
  "matcher": "Bash|Read|WebFetch",
  "hooks": [{"type": "command", "command": ".venv/bin/python .claude/hooks/truncate-output.py"}]
}
```

Tune the ceiling in `tools/search_config.py` via `MAX_TOOL_OUTPUT_CHARS` (default `4000`; set `0` to disable).

**Optional — conversation compaction trigger** (nudges `/compact` when session transcript grows large):

```json
{
  "matcher": ".*",
  "hooks": [{"type": "command", "command": ".venv/bin/python .claude/hooks/compact-trigger.py"}]
}
```

Tune in `tools/search_config.py` via `MAX_SESSION_CHARS` (default `500_000` ≈ 125k tokens; set `0` to disable). The hook has built-in hysteresis — once tripped it only re-fires after the transcript grows by another 25%.

### 3. Optional: session-start preflight

```bash
.venv/bin/python tools/embeddings.py refresh   # incremental, ~1s when nothing changed
.venv/bin/python tools/embeddings.py health    # fail fast if index is stale
```

---

## Repository layout

```
less_tokens_claude/
├── install.py                 # cross-platform installer
├── tools/
│   ├── search_config.py       # ← only file to edit when porting
│   ├── embeddings.py          # build/refresh the vector index
│   ├── search.py              # semantic search CLI
│   └── db.py                  # SQLite helpers
├── schema/
│   └── index.sql              # documents table schema
├── hooks/
│   ├── search-first.py        # PreToolUse: gate Read on indexed files
│   ├── index-refresh.py       # PostToolUse: re-embed after Edit/Write
│   ├── caveman-reminder.py    # PostToolUse: nudge back to terse output
│   ├── truncate-output.py     # PostToolUse: cap oversized Bash/Read/WebFetch results
│   └── compact-trigger.py     # PostToolUse: nudge /compact when transcript grows large
└── caveman/
    └── caveman.md             # CLAUDE.md snippet for caveman output style
```

---

## Contributing

All contributions go through Pull Requests. Discussion happens in PR comments.

- **Report a bug or request a feature** — fork, add an entry to [BACKLOG.md](BACKLOG.md), open a PR.
- **Fix something** — fork, implement the fix, open a PR.
- Both can be combined in one PR.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full workflow.

---

## License

MIT

---

## `.claudeignore`

Claude Code respects a `.claudeignore` file (same syntax as `.gitignore`) to exclude files from its project file scope — files listed there won't be surfaced as context candidates or suggested for reading.

`less_tokens` ships a `.claudeignore` that excludes files Claude doesn't need when doing code work in this repo:

| Entry | Reason |
|---|---|
| `README.md` | User-facing marketing page; content is in `documentation.md` |
| `documentation.md` | Reference docs; Claude reads source, not its own docs |
| `CHANGELOG.md` | History log; not relevant to active development |
| `bughunt/` | Bug-hunt protocol and log; not part of the core toolkit |
| `.github/` | CI workflow config; rarely needs reading during development |
| `tests/perf/latest.json` | Generated benchmark artifact |
| `caveman/caveman.md` | Template copied into target projects; not used in this repo |

**When installing into your own project**, add a `.claudeignore` at the project root to exclude any large files Claude doesn't need for its day-to-day work — test fixtures, generated output, vendored assets, docs:

```
# .claudeignore example
docs/
tests/fixtures/large_dataset/
dist/
*.lock
```

The fewer files in scope, the less noise in tool suggestions and directory listings.

---

## Known Documentation Gaps

Items tracked for future documentation improvement.

### High Priority

- **No troubleshooting section** — the three most common failure modes (fastembed download fails on first run, wrong venv path in `search_config.py`, empty index returning no results) have no documented recovery steps anywhere

### Medium Priority

- **Wiring section shows separate JSON blocks** — users must manually merge hook entries; JSON merging is a common error source; should show one complete unified `settings.local.json` block
- **`index-refresh.log` is never mentioned** — background refresh writes to `.claude/state/index-refresh.log` but this path appears nowhere; users can't diagnose silent refresh failures without reading source
- **`embeddings.py` usage examples use `python3`** — won't work on Windows and ignores the venv; should use `<venv-python> tools/embeddings.py refresh`
- **CONTRIBUTING.md verification step has no specifics** — should list concrete commands to run and what passing looks like
- **`EXCLUDED_DIR_PREFIXES` vs `EXCLUDED_DIR_NAMES` not explained** — both exclude dirs but via different mechanisms; distinction trips up new users
- **`WINDOW_SECONDS` not documented** — the 5-minute search-gate window is mentioned in passing; no explanation it's hardcoded or where to change it
- **Empty search result behavior not explained** — README mentions fallback conditions but not whether the gate lifts automatically or Claude must detect the empty result
- **CHANGELOG format vs `chunk_changelog` mismatch not noted** — chunker's date-only regex won't match `## [version] - date` headers; developers won't know the index is silently not splitting correctly

### Low Priority

- **Animated GIF demo** — screencast showing before/after: full Read vs. search returning targeted chunks
- **Token savings benchmarks** — documented measurements on a real codebase showing actual reduction
