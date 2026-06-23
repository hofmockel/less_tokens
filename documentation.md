# Documentation

Full reference for installing, configuring, and using `less_tokens`.

---

## Prerequisites

- Python 3.9+
- A virtual environment for your project (`.venv`, `venv`, `env`, or `app/.venv`)
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed

---

## Installation

Clone less_tokens *into* the project you want to install it on. The installer targets the parent directory of the clone, so it works from any cwd:

```bash
# macOS / Linux
cd ~/myproject
git clone https://github.com/<you>/less_tokens.git
python3 less_tokens/install.py

# Windows
cd C:\myproject
git clone https://github.com/<you>/less_tokens.git
python less_tokens\install.py
```

Re-running after `git pull` performs an in-place upgrade — existing files are skipped, hook wiring is deduplicated, and `search_config.py` only gains any new variables. Nothing local is overwritten unless you pass an explicit `--force*` flag.

> By default the installer skips the index build so you can configure `search_config.py` first. Pass `--build` to build immediately (step 3 below covers manual build).

The installer copies tools and schema into `.claude/tools/` and `.claude/schema/`, deploys hooks into `.claude/hooks/`, installs `fastembed` and `numpy`, and initializes `.claude/index.db`.

**Optional flags:**

| Flag | Effect |
|---|---|
| `--target PATH` | Install into PATH instead of the parent of the clone (testing / scratch projects) |
| `--yes` | Bypass the suspicious-target sanity check (fires when parent is `/` or `$HOME`) |
| `--force` | Overwrite existing files |
| `--venv PATH` | Point to a venv not in a standard location |
| `--skip-deps` | Skip `pip install` (dependencies already installed) |
| `--build` | Build the index immediately after install |
| `--agent claude\|codex\|both` | Agent target: Claude Code (default), Codex, or both simultaneously |
| `--caveman` | Also copy `.claude/rules/` (caveman output style) |
| `--truncate` | Wire the tool output truncation hook |
| `--compact` | Wire the conversation compaction trigger hook |

---

## Codex support

`--agent codex` (or `--agent both`) installs Codex adapter hooks under `.codex/hooks/` when that directory is writable. `.less_tokens/` is the shared product runtime: it holds the budget control-plane config, budget engine, telemetry state, report tools, and Codex command shims. The underlying index remains the shared project index at `.claude/index.db`, so Claude and Codex can search the same local corpus without maintaining two databases.

```bash
python3 less_tokens/install.py --agent codex
python3 less_tokens/install.py --agent both   # Claude + Codex simultaneously
```

**What gets installed:**

| Path | Purpose |
|---|---|
| `.less_tokens/config/budget.json` | Shared budget-control config for Claude and Codex |
| `.less_tokens/hooks/budget/` | Shared budget engine used by both agent adapters |
| `.less_tokens/tools/` | Codex command shims that run the single `.claude/tools/` implementation |
| `.less_tokens/tools/budget_report.py` | v2 budget telemetry report |
| `.less_tokens/tools/budget_doctor.py` | config and recent-pressure diagnosis |
| `.less_tokens/bin/python` | Venv-backed Python launcher for Codex commands |
| `.less_tokens/schema/` | SQLite schema |
| `.less_tokens/hooks/` | Shared hook support imported by Codex adapters |
| `.less_tokens/state/` | Shared budget telemetry plus Codex runtime state |
| `.codex/hooks/` | Codex adapter hooks (wired to `.codex/hooks.json` when writable) |
| `AGENTS.md` | Token-discipline fragment appended via HTML comment sentinels |
| `.less_tokens/skills/less-tokens/` | Fallback skill path when `.codex/` is not writable |
| `.claude/index.db` | Shared vector index used by both agents |

**Compatibility:**

| Feature | Claude | Codex |
|---|---|---|
| Vector search + index | ✓ stable | ✓ stable |
| Search-before-read | ✓ enforced via hook | best-effort via `.codex/hooks.json` |
| Auto-sliced reads | ✓ enforced via hook | best-effort via `.codex/hooks.json` |
| Noise-file and large-read guards | ✓ enforced via hook | best-effort via `.codex/hooks.json` |
| Context-cache reread guard | ✓ enforced via hook | best-effort via `.codex/hooks.json` |
| Post-edit diff and reread block | ✓ enforced via hook | best-effort via `.codex/hooks.json` |
| Recursive listing guard | ✓ enforced via hook | best-effort via `.codex/hooks.json` |
| Structured Bash output parsers | ✓ enforced via hook | best-effort via `.codex/hooks.json` |
| Tool-output truncation | ✓ optional hook | best-effort optional hook |
| Compaction trigger | ✓ optional hook | best-effort optional hook |
| Symbol lookup | ✓ Python + JS/TS | ✓ Python + JS/TS |
| AGENTS.md / CLAUDE.md pruning | ✓ | ✓ (`agentsmd_audit.py`) |

**Known limitations:**

- Codex hook enforcement is best-effort — interception depends on `.codex/hooks.json` being writable and Codex emitting the expected tool events. If `.codex/` is not writable at install time, the skill and `AGENTS.md` fragment are installed but hooks are skipped.
- `.codex/hooks.json` write is optional — install always exits 0 regardless of hook wiring success.
- Budget telemetry lives in `.less_tokens/state/events.jsonl` for both agents. Codex runtime state also lives in `.less_tokens/state/`; older Claude search state remains in `.claude/state/`. The vector index is shared at `.claude/index.db`.
- Caveman output style (`--caveman`) wires Claude's Stop hook and Codex's concise-reminder hook; Codex enforcement remains best-effort like the other Codex hooks.

See [codex-hook-coverage.md](codex-hook-coverage.md) for the exact Codex hook matrix, including which strategies are wired by default and which remain optional.

For repeatable savings checks, run:

```bash
.claude/bin/python .claude/tools/eval_sessions.py --report .claude/state/session-eval.md
```

The harness is deterministic and fixture-based; it is useful for trend tracking, not a substitute for live Claude/Codex usage data.

---

## Configuration

Search and indexing are configured in `.claude/tools/search_config.py`. Budget behavior is configured separately in `.less_tokens/config/budget.json`. Codex commands under `.less_tokens/tools/` are compatibility shims that import and run the same `.claude/tools/` search code, so `.less_tokens/tools/search_config.py` is not a separate source of truth.

The installer prints the exact line to paste in. At minimum, set your venv path and the source directories to index:

```python
# .claude/tools/search_config.py

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
| `TRACK_SAVINGS` | Enable per-strategy savings logging (default `False`; set via `.claude/bin/python .claude/tools/stats.py --enable`) |

`INDEXED_SOURCE_DIRS` also feeds JS/TS indexing for `.js`, `.jsx`, `.ts`, and `.tsx` files.

### Budget control plane

The budget control plane scores proposed context before it enters the agent transcript. It can replace broad reads with targeted slices, summarize oversized tool output, defer low-value context, block repeated reads/searches, and trigger pressure-based compaction snapshots.

Configure it in `.less_tokens/config/budget.json`:

| Mode | Behavior |
|---|---|
| `observe` | Record v2 telemetry only; never changes hook behavior |
| `advise` | Record telemetry and print concise suggestions |
| `enforce` | Block actionable waste when a replacement or bypass path exists |
| `strict` | Enforce plus block oversized unscored context |

The default mode is `observe`. Events are appended to `.less_tokens/state/events.jsonl`; compact per-agent session snapshots are written beside it, such as `.less_tokens/state/claude-session.json` and `.less_tokens/state/codex-session.json`.

Inspect budget behavior with:

```bash
.claude/bin/python .less_tokens/tools/budget_report.py
.claude/bin/python .less_tokens/tools/budget_doctor.py
```

For Codex-only installs, the same tools can be run through the Codex launcher:

```bash
.less_tokens/bin/python .less_tokens/tools/budget_report.py
.less_tokens/bin/python .less_tokens/tools/budget_doctor.py
```

Use the escape hatch only when the agent truly needs the broad context: set `less_tokens_bypass: true`, set `tool_input.less_tokens_bypass: true`, or include `less_tokens: allow` / `less_tokens: bypass` in string input.

---

## Usage

### Build the index

Run this once after configuring, and again whenever you want a full refresh:

```bash
.claude/bin/python .claude/tools/embeddings.py refresh
```

For Codex-only workflows, `.less_tokens/bin/python .less_tokens/tools/embeddings.py refresh` remains supported as a shimmed command path.

> First run downloads the embedding model (~130 MB to `~/.cache/huggingface`). Subsequent runs are incremental and typically take under a second.

### Search

```bash
.claude/bin/python .claude/tools/search.py "your query"
```

For Codex-only workflows, `.less_tokens/bin/python .less_tokens/tools/search.py` remains supported as a shimmed command path.

**Examples:**

```bash
.claude/bin/python .claude/tools/search.py "how are imports validated"
.claude/bin/python .claude/tools/search.py "cash floor logic" --source-type code
.claude/bin/python .claude/tools/search.py "deployment steps" -k 5 --json
```

### Verify the index

```bash
.claude/bin/python .claude/tools/embeddings.py health   # exits 1 if any source has no chunks
.claude/bin/python .claude/tools/db.py verify           # prints row counts per source type
```

### Token savings tracking

Track how many chars and tokens each strategy saves across a session.

Tracking is **off by default**. Enable it with:

```bash
.claude/bin/python .claude/tools/stats.py --enable    # non-interactive
# or
.claude/bin/python .claude/tools/stats.py             # interactive prompt
```

Once enabled, each hook call appends one JSON record to `.claude/state/savings.jsonl`.

**Commands:**

```bash
.claude/bin/python .claude/tools/stats.py              # show session table (last 8h)
.claude/bin/python .claude/tools/stats.py --all        # show all-time totals
.claude/bin/python .claude/tools/stats.py --report     # write .claude/state/savings-report.md and print table
.claude/bin/python .claude/tools/stats.py --disable    # turn tracking off
```

Also accessible as:

```bash
.claude/bin/python .claude/tools/embeddings.py savings
```

**Example output:**

```
## Session (last 8h · 8 events)

| Strategy               | Events |  Chars saved |  ~Tokens saved |
|------------------------|--------|--------------|----------------|
| Truncation             |      3 |       18,100 |          4,525 |
| Search-first block     |      2 |       22,600 |          5,650 |
| Search (vs full file)  |      2 |       20,300 |          5,075 |
| Compaction nudges      |      1 |            — |              — |
|------------------------|--------|--------------|----------------|
| **Total**              |        | **61,000**   |     **15,250** |
```

Token estimates use 4 chars ≈ 1 token. Search savings compare chunk text returned against the full size of matched files on disk.

### Caveman mode

Append the caveman snippet to your `CLAUDE.md` to enforce terse output:

```bash
cat .claude/rules/caveman.md >> CLAUDE.md
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

    .claude/bin/python .claude/tools/search.py "QUERY"

Indexed sources: [list your dirs here]

Use `Read` directly only when search returns no relevant chunks,
when you need to edit a file, or when the index is unavailable.
```

### 2. Add hooks to `.claude/settings.local.json`

The installer writes `.claude/bin/python` as a venv-backed launcher, so hook commands do not depend on system Python packages.

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Read",
        "hooks": [{"type": "command", "command": ".claude/bin/python .claude/hooks/search-first.py"}]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [{"type": "command", "command": ".claude/bin/python .claude/hooks/index-refresh.py"}]
      }
    ]
  }
}
```

**Optional — caveman nudge hook** (fires if Claude uses verbose filler):

```json
{
  "matcher": ".*",
  "hooks": [{"type": "command", "command": ".claude/bin/python .claude/hooks/caveman-reminder.py"}]  // Stop event
}
```

**Optional — tool output truncation hook** (caps oversized Bash/Read/WebFetch results). Add as another `PostToolUse` entry, **before** the caveman entry if both are present:

```json
{
  "matcher": "Bash|Read|WebFetch",
  "hooks": [{"type": "command", "command": ".claude/bin/python .claude/hooks/truncate-output.py"}]
}
```

Tune the ceiling in `.claude/tools/search_config.py` via `MAX_TOOL_OUTPUT_CHARS` (default `4000`; set `0` to disable).

**Optional — conversation compaction trigger** (nudges `/compact` when session transcript grows large):

```json
{
  "matcher": ".*",
  "hooks": [{"type": "command", "command": ".claude/bin/python .claude/hooks/compact-trigger.py"}]
}
```

Tune in `.claude/tools/search_config.py` via `MAX_SESSION_CHARS` (default `500_000` ≈ 125k tokens; set `0` to disable). The hook has built-in hysteresis — once tripped it only re-fires after the transcript grows by another 25%.

### 3. Optional: session-start preflight

```bash
.claude/bin/python .claude/tools/embeddings.py refresh   # incremental, ~1s when nothing changed
.claude/bin/python .claude/tools/embeddings.py health    # fail fast if index is stale
```

---

## Repository layout

All source lives under `.claude/` — the same structure that gets deployed into host projects.

**Source repo** (`less_tokens/`):
```
less_tokens/
├── install.py                 # cross-platform installer
└── .claude/
    ├── hooks/                 # deployed to <host>/.claude/hooks/
    │   ├── search-first.py        # PreToolUse: gate Read on indexed files
    │   ├── index-refresh.py       # PostToolUse: re-embed after Edit/Write
    │   ├── caveman-reminder.py    # Stop: nudge back to terse output
    │   ├── truncate-output.py     # PostToolUse: cap oversized Bash/Read/WebFetch results
    │   └── compact-trigger.py     # PostToolUse: nudge /compact when transcript grows large
    ├── rules/                 # deployed to <host>/.claude/rules/
    │   └── caveman.md             # CLAUDE.md snippet for caveman output style
    ├── schema/                # deployed to <host>/.claude/schema/
    │   └── index.sql              # documents table schema
    ├── skills/                # Claude Code skills (not deployed; dev tooling only)
    │   └── bug-hunt/
    │       └── SKILL.md           # bug-hunt protocol and round log
    ├── tests/                 # test suite (not deployed)
    │   ├── unit/
    │   ├── integration/
    │   └── perf/
    └── tools/                 # deployed to <host>/.claude/tools/
        ├── search_config.py       # ← only file to edit after install
        ├── embeddings.py          # build/refresh the vector index
        ├── search.py              # semantic search CLI
        ├── db.py                  # SQLite helpers
        ├── savings_log.py         # per-event savings logger (used by hooks)
        └── stats.py               # savings tracker CLI (enable / report / disable)
```

**Deployed layout** (inside the host project's `.claude/`):
```
<host-project>/
├── .claude/
│   ├── .venv-tokens/          # isolated Python env for fastembed/numpy
│   ├── bin/python             # venv-backed launcher for Claude commands
│   ├── hooks/                 # hook scripts (wired in settings.json)
│   ├── index.db               # SQLite vector index (regenerable)
│   ├── rules/                 # caveman.md (if --caveman was passed)
│   ├── schema/                # index.sql schema
│   ├── state/                 # runtime state (last-search, logs)
│   └── tools/                 # search_config.py, embeddings.py, search.py, …
├── .less_tokens/              # shared budget control plane + Codex runtime
│   ├── bin/python             # venv-backed launcher for Codex commands
│   ├── config/budget.json     # observe/advise/enforce/strict budget config
│   ├── hooks/budget/          # shared budget engine
│   ├── hooks/                 # shared hook support for Codex adapters
│   ├── schema/
│   ├── state/                 # events.jsonl and per-agent session state
│   └── tools/                 # budget tools plus compatibility shims
├── .codex/hooks/              # Codex adapters when .codex is writable
├── AGENTS.md                  # Codex token-discipline block
└── less_tokens/               # the clone; not touched after install
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
| `.github/` | CI workflow config; rarely needs reading during development |
| `.claude/tests/perf/latest.json` | Generated benchmark artifact |

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

- **No troubleshooting section** — the three most common failure modes (fastembed download fails on first run, wrong venv path in `.claude/tools/search_config.py`, empty index returning no results) have no documented recovery steps anywhere

### Medium Priority

- **Wiring section shows separate JSON blocks** — users must manually merge hook entries; JSON merging is a common error source; should show one complete unified `settings.local.json` block
- **`index-refresh.log` is never mentioned** — background refresh writes to `.claude/state/index-refresh.log` but this path appears nowhere; users can't diagnose silent refresh failures without reading source
- **`embeddings.py` usage examples use `python3`** — won't work on Windows and ignores the venv; should use `.claude/bin/python .claude/tools/embeddings.py refresh`
- **CONTRIBUTING.md verification step has no specifics** — should list concrete commands to run and what passing looks like
- **`EXCLUDED_DIR_PREFIXES` vs `EXCLUDED_DIR_NAMES` not explained** — both exclude dirs but via different mechanisms; distinction trips up new users
- **`WINDOW_SECONDS` not documented** — the 5-minute search-gate window is mentioned in passing; no explanation it's configurable in `.claude/tools/search_config.py`
- **Empty search result behavior not explained** — README mentions fallback conditions but not whether the gate lifts automatically or Claude must detect the empty result
- **CHANGELOG format vs `chunk_changelog` mismatch not noted** — chunker's date-only regex won't match `## [version] - date` headers; developers won't know the index is silently not splitting correctly

### Low Priority

- **Animated GIF demo** — screencast showing before/after: full Read vs. search returning targeted chunks
- **Token savings benchmarks** — documented measurements on a real codebase showing actual reduction

---

## Architecture internals

_Moved from CLAUDE.md to keep that file lean. Indexed — reachable by search._

The source tree has a Claude runtime, a Codex adapter layer, and shared hook logic:

```
.claude/
  hooks/           ← PreToolUse / PostToolUse / Stop hooks
  rules/           ← Output style rules (caveman.md)
  skills/          ← Claude Code skills (bug-hunt, claudemd)
  tools/           ← Core Python scripts deployed to host projects
  schema/          ← SQL schema deployed to host projects
  tests/           ← Unit, integration, and perf test suites
  commands/        ← /build-index, /search, /def slash commands
agents/
  common/hooks/    ← agent-neutral hook checks used by adapters
  codex/hooks/     ← thin Codex hook adapters
  codex/skills/    ← Codex skills
```

### Layer split

**Agent-agnostic core (`.claude/tools/` and `.claude/schema/`)**
- `.claude/tools/search_config.py` — the single config file users edit; all runtime constants live here including `VENV_PY`, `INDEXED_SOURCE_DIRS`, `STATE_DIR`, truncation limits, compaction threshold
- `.claude/tools/embeddings.py` — chunks source files by structure (Python AST, markdown headings, SQL statements, JS/TS declarations), embeds with `BAAI/bge-small-en-v1.5` via `fastembed`, upserts into `.claude/index.db` with content-hash diffing
- `.claude/tools/search.py` — cosine similarity search over stored float32 vectors; writes `STATE_DIR/last-search` on every run so the search-first gate knows a search occurred
- `.claude/tools/db.py` — SQLite helpers; `connect_index()` opens `.claude/index.db`
- `.claude/tools/symbols.py` — exact symbol index for Python and JS/TS; `symbols.py <name>` (and the `/def` command) returns a definition's exact `file:line` + a `Read(offset,limit)`, no grep dump. Self-creating `symbols` table; refreshes when sources change
- `.less_tokens/tools/*.py` — generated Codex compatibility shims; these keep existing Codex command paths working while `.claude/tools/` remains the single implementation and config source.
- `.claude/schema/index.sql` — `documents` table with `(source_path, source_key)` unique constraint; `embedding_model` column exists per row for planned multi-model support

**Budget control plane (`.less_tokens/`)**
- `.less_tokens/config/budget.json` — mode, total context budget, category limits, hard caps, and per-agent overrides
- `.less_tokens/hooks/budget/` — shared budget package: candidate normalization, relevance scoring, selection, advice/enforcement outcomes, compaction snapshots, and event logging
- `.less_tokens/state/events.jsonl` — v2 telemetry for considered, selected, rejected, transformed, and compacted context
- `.less_tokens/tools/budget_report.py` — savings, omissions, transformations, quality-risk, and compaction report
- `.less_tokens/tools/budget_doctor.py` — current config and recent pressure diagnosis

**Claude Code hook layer (`.claude/hooks/`)**
- All hooks read a JSON payload from stdin and exit `0` (pass) or `2` (block/replace)
- `.claude/hooks/search-first.py` — PreToolUse on `Read` (blocks if the file is indexed and no search ran within `WINDOW_SECONDS`, 300s) and on `Grep` (non-blocking: if the pattern is a known symbol, suggests `/def` for the exact location)
- `.claude/hooks/read-guard.py` — PreToolUse on `Read`; blocks an un-sliced Read of a noise file (lockfile/minified/binary/oversized data) per `READ_DENY_GLOBS` + `READ_DENY_DATA_MAX_LINES`; a Read with an `offset` is allowed
- `.claude/hooks/auto-slice.py` — PreToolUse on `Read`; if the file was a hit in the last (recent) search, blocks an un-sliced Read with the exact `Read(offset, limit)` for the matched range (`STATE_DIR/last-search.json`, written by `search.py`); pass `offset` to override
- `.claude/hooks/index-refresh.py` — PostToolUse on `Edit|Write`; fires `embeddings.py refresh` as a detached background process; logs to `.claude/state/index-refresh.log`
- `.claude/hooks/truncate-output.py` — PostToolUse on `Bash|Read|WebFetch`; caps output at `MAX_TOOL_OUTPUT_CHARS` (Bash uses head+tail lines; others use 60/40 char split)
- `.claude/hooks/compact-trigger.py` — PostToolUse on `.*`; checks `transcript_path` size; 25% hysteresis via `.claude/state/compact-trigger-last`
- `.claude/hooks/caveman-reminder.py` — Stop hook; reads the last assistant turn from `transcript_path` and exits 2 if it contains filler or exceeds `MAX_RESPONSE_WORDS` (code fences exempt); `stop_hook_active` guard prevents loops
- `.claude/hooks/claudemd-budget.py` — PostToolUse on `Edit|Write`; blocks when CLAUDE.md exceeds `CLAUDE_MD_TOKEN_BUDGET` or gains a stale ref

**Codex hook layer (`agents/codex/hooks/`)**
- Thin adapters normalize Codex payloads, call shared checks where available, and write state under `.less_tokens/state/`.
- Default adapters cover search-first, read guard, auto-slice, grep-first read, read-after-edit, context cache, listing guard, lean-output, post-edit diff, index refresh, and AGENTS.md budget checks.
- Optional adapters cover truncation, compaction, and terse-output reminders when their install flags are enabled.
- See [codex-hook-coverage.md](codex-hook-coverage.md) for event matchers and known limits.

**Rules (`.claude/rules/`)**
- `.claude/rules/caveman.md` — caveman output style guide; append to `CLAUDE.md` with `--caveman` install flag
- Audit always-loaded or appendable rule files with `.claude/bin/python .claude/tools/claudemd_audit.py --rules`; the per-file default cap is `RULES_TOKEN_BUDGET`.

**Skills (`.claude/skills/`)**
- `.claude/skills/bug-hunt/SKILL.md` — bug-hunt protocol: severity rubric, stop rule, agent prompt template
- `.claude/skills/claudemd/SKILL.md` — prune CLAUDE.md to only what must be always-loaded

Hooks are unit-tested by importing them as modules via `.claude/tests/conftest.py:load_hook()` (it puts `.claude/tools/` on `sys.path` so the source tools are importable during tests, then execs the hook file). Keep hook logic importable — no side effects at module load.

### State directory

`STATE_DIR` in `search_config.py` is `CLAUDE_DIR / "state"` (i.e., `.claude/state/` in the host project).

### Chunking strategies

| File type | Strategy | Key unit |
|---|---|---|
| `.py` | `chunk_python` — AST parse | top-level `def`/`class`/`UPPER_CASE` |
| `.js`/`.jsx`/`.ts`/`.tsx` | `chunk_js` — declaration scan | functions/classes/consts/interfaces/enums/types |
| `.md` | `chunk_markdown` — regex H1/H2/H3 | heading sections |
| `CHANGELOG.md` | `chunk_changelog` — version/date headers | Keep a Changelog and date headers |
| `.sql` | `chunk_sql` — split on `;\n` | CREATE TABLE/VIEW/INDEX name |

### End-to-end verification

For hook behavior and the full install path, verify against a scratch project:

```bash
# Install into a scratch project. The installer targets the parent of this clone — cwd doesn't matter.
python3 install.py --build
# Override the target:
python3 install.py --target /path/to/scratch --yes --build
# Build the local index (requires fastembed)
.claude/bin/python .claude/tools/embeddings.py refresh
# Search
.claude/bin/python .claude/tools/search.py "your query"
.claude/bin/python .claude/tools/search.py "query" --source-type code -k 5 --json
# Index health
.claude/bin/python .claude/tools/embeddings.py health
.claude/bin/python .claude/tools/db.py verify
```
