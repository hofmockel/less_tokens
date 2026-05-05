# Backlog

## Purpose

This file is the single source of truth for planned work — new features, bug fixes, and improvements that have been identified but not yet started. It exists so that anyone (contributor, maintainer, or user) can see what's coming, understand priorities, and avoid duplicating effort.

## How to use it

All contributions go through Pull Requests — see [CONTRIBUTING.md](CONTRIBUTING.md) for the full workflow.

**Reporting a bug or requesting a feature?**
Fork the repo, add an entry to this file in the appropriate section (`## Bugs` for bugs, the relevant feature section otherwise), and open a PR. Include a file:line reference for bugs. Discussion happens in PR comments.

**Picking up work?**
Fork the repo, implement the fix, and open a PR. Adding the backlog entry and fixing it can be one PR.

**When work ships — the maintainer:**

1. Adds a CHANGELOG entry under `[Unreleased]` in the appropriate Keep-a-Changelog section (`### Added` / `### Changed` / `### Fixed` / `### Removed` / `### Deprecated` / `### Security`), written from the user's perspective.
2. Deletes the item from this file before merging. No strikethrough, no "DONE" marker — the absence is the signal.

The README is the source of truth for what the project *is today*; the backlog is the source of truth for what it *isn't yet*. Anything appearing in both is a bookkeeping bug — fix it by removing the backlog entry.

**Priority definitions:**

| Level | Meaning |
|---|---|
| **High** | Clear value, known implementation path — good first targets |
| **Medium** | Important but less urgent; may need more design thought |
| **Low / Ideas** | Worth tracking, no commitment to timeline |

---

## Bugs

Confirmed defects found by code inspection. Each has a specific file and line reference.

- **`chunk_changelog` regex won't match this repo's own CHANGELOG** — the splitter expects `## YYYY-MM-DD` but Keep a Changelog format (and our `CHANGELOG.md`) uses `## [0.2.0] - 2026-05-03`. Every version section silently falls back to `chunk_markdown`, losing the date-based key structure. (`tools/embeddings.py:147`)

- **`is_indexed()` exclusion logic differs between `search-first.py` and `index-refresh.py`** — `search-first.py` uses `("/" + d) in ("/" + rel) or rel.startswith(d)` which matches excluded names anywhere in the path; `index-refresh.py` uses only `rel.startswith(d)`. The two hooks will disagree on whether mid-path excluded directories are blocked. (`hooks/search-first.py:49`, `hooks/index-refresh.py:37`)

- **`search_config.py` default `INDEXED_SOURCE_DIRS` includes `"app/"` which is never created by the installer** — fresh install targets will have `health` report a gap for every file under `app/` until the user edits the config. The default should only include directories the installer actually creates (`tools/`, `schema/`). (`tools/search_config.py:38`)

- **`db.py` `verify()` interpolates table name directly into SQL** — `f"SELECT COUNT(*) FROM {r[0]}"` constructs SQL from `sqlite_master` output without sanitization. Low real-world risk but bad practice; should use a whitelist or quoted identifier. (`tools/db.py:64`)

- **`start_new_session=True` is a no-op on Windows in `index-refresh.py`** — `subprocess.Popen(..., start_new_session=True)` is documented as POSIX-only; on Windows the kwarg is ignored and the child remains attached to the parent, defeating the detach intent. Fix: branch on `sys.platform`; on Windows pass `creationflags=subprocess.DETACHED_PROCESS` (or `CREATE_NEW_PROCESS_GROUP`) instead. (`hooks/index-refresh.py:72`)

- **Venv path containing `"` produces invalid Python in the printed `VENV_PY` line** — `f'       VENV_PY = _venv_python("{venv_dir}")'` interpolates the path raw; a path with an embedded `"` yields a `SyntaxError` when the user pastes it. Fix: emit `repr(str(venv_dir))` or `json.dumps(str(venv_dir))` so escaping is correct. (`install.py:189-190`)

- **`--source-type` argparse `choices` may drift from values actually stored in `documents.source_type`** — argparse rejects valid values present in older databases (or accepts values no longer produced) because the choices list and the column are two unsynchronised sources of truth. Fix: derive choices from `SELECT DISTINCT source_type FROM documents` at runtime, or add a `CHECK` constraint to `index.sql` that pins the vocabulary. (`tools/search.py:70`)

- **Vectors stored in native byte order — `index.db` is not portable across endianness** — `np.float32.tobytes()` writes host-native bytes; `np.frombuffer(..., dtype=np.float32)` reads with the host's endianness. A db built on little-endian and read on big-endian (POWER, s390x, some embedded ARM) returns silently wrong cosine scores. Fix: pin dtype to `<f4` (little-endian) on both write and read paths. (`tools/embeddings.py:296`, `tools/search.py:46`)

- **`enumerate_sources()` aborts the entire refresh on a single permission-denied directory** — `path.rglob("*")` propagates `PermissionError` from a single unreadable subtree, killing the run and leaving the index stale. Fix: wrap each per-source enumeration in `try/except OSError`, log a warning, and continue. (`tools/embeddings.py:173`)

- **Heading-dedup `_2` suffix can collide with a literal `## Foo_2` in the same file** — the dedup logic renames repeats to `Foo_2`, but if the source already contains `## Foo_2` literally, both end up with identical `(source_path, source_key)` and the UPSERT silently overwrites. Fix: pre-scan all heading keys for the file and only suffix when the candidate is free, or use an ordinal scheme (`Foo#2`) using a character that cannot appear in a markdown heading. (`tools/embeddings.py:94-99`)

- **`chunk_sql` splits on `;` inside SQL line comments** — `re.split(r";\s*\n", src)` treats a `-- explanation; with semicolon\n` as a statement boundary; the next real statement loses its `CREATE TABLE` / `CREATE INDEX` prefix and is keyed as `stmt:<hash>` instead of `table:foo`, hurting search quality. Fix: strip line-comments before splitting, or use a real SQL tokeniser. (`tools/embeddings.py:136`)

---

## Bug-Hunt Protocol

See [bughunt.md](bughunt.md) for the full protocol — severity rubric, stop rule, and agent prompt template.
Hunt statistics are recorded round-by-round in [bughuntlog.md](bughuntlog.md).

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
- **Implement graceful degradation** — explicit handlers in `tools/embeddings.py` and `tools/search.py` for each failure condition (see Design Notes); each catches the failure, emits a structured warning to stderr, and continues rather than propagating an exception.
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

### High Priority

- **Regression test suite (`tests/unit/`)** — `pytest` unit tests covering every component that has broken silently in the past or has known edge-case bugs:
  - Chunkers: `chunk_python` (AST fallback on syntax error, UPPER_CASE constants, nested classes), `chunk_markdown` (H1/H2/H3 nesting, heading dedup collision), `chunk_sql` (semicolons inside line comments), `chunk_changelog` (Keep-a-Changelog header format vs. date-only format)
  - `is_indexed()` parity — assert that `search-first.py` and `index-refresh.py` return identical results for the same path/config pairs; this directly catches the mid-path exclusion divergence bug
  - Incremental refresh hash logic — modify a source file, run refresh, assert only the changed chunk is replaced
  - Config merging (`merge_search_config`) — missing variable added, existing variable preserved, comment block preserved
  - Settings wiring (`wire_settings`) — idempotent on second call, correct JSON structure, no duplicates
  - Hook protocol — feed synthetic stdin payloads to each hook script; assert exit code and stdout JSON for block (exit 2) and pass (exit 0) cases

- **Installation test harness (`tests/integration/test_install.py`)** — end-to-end install into a `tmp_path` scratch directory; one test per install path:
  - Fresh install: assert all expected files present, `settings.local.json` correctly wired, `search_config.py` has correct `VENV_PY`
  - Re-install without `--force`: assert existing files are untouched (checksum preserved)
  - Re-install with `--force` but without `--overwrite-modified`: assert modified files are skipped with a diff-summary warning
  - Re-install with `--force --overwrite-modified`: assert modified files are replaced and diff is printed
  - Config merge: install with a `search_config.py` missing a new variable; assert variable is appended without touching existing lines
  - `--check` flag: assert exit 0 when valid, exit 1 with specific message for each failure mode (missing venv, missing `index.db`, hook not wired)

- **Token performance benchmark (`tests/perf/bench_tokens.py`)** — measures the actual token-cost reduction each strategy delivers; run manually or in CI on a representative fixture codebase:
  - Fixture: a small synthetic project with ~20 source files (~500 lines each) committed under `tests/fixtures/sample_project/`
  - **Pre-install baseline** — count characters (and estimated tokens via `len(text) / 4`) consumed by reading every file returned by a set of 10 benchmark queries using `Read`
  - **Post-install (search)** — for the same 10 queries, count characters in the top-k search results returned by `search.py`
  - **Truncation savings** — for 5 synthetic oversized Bash/Read outputs, measure character count before and after `truncate-output.py` processes them
  - **Compaction trigger** — verify `compact-trigger.py` fires (exit 2 with message) when transcript size exceeds `MAX_SESSION_CHARS` and does not fire below threshold
  - Report format: one row per strategy — `strategy | before_chars | after_chars | reduction_%`; assert reduction meets minimum thresholds (vector search ≥ 70%, truncation ≥ 40%) to catch regressions in search quality or hook behaviour
  - Emit results to `tests/perf/latest.json` so CI can track trend over time

### Medium Priority

- **CI: test on Python 3.9 / 3.11 / 3.12** — GitHub Actions matrix running `tests/unit/` and `tests/integration/` on all three versions and all three OS (ubuntu / macos / windows); `tests/perf/` runs on ubuntu only to keep CI times down
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

Candidate token-reduction approaches not yet implemented. Evaluate and promote to High Priority once design is agreed.

### Strategy 6 — Tiered Effort

**Concept:** Token cost has two independent levers — the *Claude model* chosen and the *effort* applied (output length, reasoning depth, tool call count). Routing a mechanical task to Haiku at minimal effort vs. Opus at full effort can differ 10–20× in cost. The tier abstraction maps task complexity to the right combination of both.

**Three tiers:**

| Tier | Model | Effort | Trigger examples |
|---|---|---|---|
| **L1 Mechanical** | `claude-haiku-4-5` | Minimal — one confirmation, no tables, no summaries | File operations, index refresh, status checks, renames |
| **L2 Rules** | `claude-sonnet-4-6` | Medium — result + brief reasoning, tables only if ≥3 rows | Search queries, config edits, doc updates, targeted bug fixes |
| **L3 Planning** | `claude-opus-4-7` | Full — analysis, options, tradeoffs | Architecture decisions, new strategies, refactors, reviews |

**Proactive suggestion:** Before each task the agent emits one line stating the recommended tier — but only when it changes from the prior turn: `"L1 — recommend Haiku, minimal effort."` Silence when the tier holds.

**Model switching:** `/model <alias>` slash command in Claude Code.

**Implementation:**

- `caveman/tier-matrix.md` — task-type → tier mapping, appended to `CLAUDE.md` like `caveman.md`.
- `search_config.py` additions — `AGENT_TIER_HINTS: bool = True` to toggle the proactive hint line.
- Extends the `AGENT_MODEL` variable proposed in Vector Search & Indexing above.

**Expected savings:** 50–70% blended reduction on mixed sessions.

**New files:** `caveman/tier-matrix.md`
**Modified files:** `search_config.py`, `caveman/caveman.md` (cross-reference)

---

### Strategy 4 — Prompt Caching *(deferred — likely redundant with Claude Code defaults)*

**Original problem:** On every Claude Code session the system prompt, `CLAUDE.md`, and any large context blocks (architecture docs, schema files) are re-sent in full, consuming thousands of input tokens even though they haven't changed.

**Why deferred:** Claude Code already uses Anthropic's prompt caching automatically for the system prompt and `CLAUDE.md` — adding a manual `cache-primer.py` would mostly duplicate built-in behavior. Revisit only if either of these becomes true:

- Measurement on a real session shows the auto-cache is missing meaningful content (large doc files Claude reads every turn that don't fit the auto-cached prefix).

**Original approach (kept for reference):** Structure the system prompt and `CLAUDE.md` to take advantage of [Anthropic's prompt caching](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching) — place stable, large blocks at the top of the context in the cacheable position. Provide a `cache-primer.py` script users run at session start to warm the cache with their most-read files. Up to 90% reduction on the cached portion when the auto-cache *isn't* doing the job already.

---

## Design Notes: Embedding Model

Reference material for the Vector Search & Indexing work items above.

### Current constraints

- `MODEL` and `DIM` are hardcoded constants in `tools/embeddings.py:39-40`.
- `search.py:44` reshapes all stored vectors using the hardcoded `DIM=384`. A model producing a different dimension silently corrupts results.
- The `embedding_model` column already exists per-row in `index.db` but is never used to drive search.
- Changing the model invalidates every vector in the index and requires a `--full` refresh.

### Available embedding models (fastembed, local)

| Option | Model | Dim | Size |
|---|---|---|---|
| **Small** *(current default)* | `BAAI/bge-small-en-v1.5` | 384 | ~130 MB |
| **Large** | `BAAI/bge-large-en-v1.5` | 1024 | ~1.2 GB |
| **Keyword fallback** | BM25 / TF-IDF (stdlib) | — | 0 MB |

### Graceful degradation targets

| Condition | Current behaviour | Target behaviour |
|---|---|---|
| `fastembed` not installed | `RuntimeError`, refresh aborts | Fall back to keyword search with a one-time warning |
| Model download fails (offline) | Exception, index empty | Use last successfully cached model; warn if none cached |
| `index.db` missing or empty | `search-first` gate fires, no results | Gate lifts automatically; Claude proceeds with `Read` and a one-time advisory |
| DB locked by concurrent refresh | `sqlite3.OperationalError` | Retry once with 500ms backoff; return stale results on second failure with a warning |
