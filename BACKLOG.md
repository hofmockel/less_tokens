# Backlog

Planned work not yet started. Maintainer: add `CHANGELOG.md` entry + delete item here before merging. See [bughunt/bughunt.md](bughunt/bughunt.md) / [bughunt/bughuntlog.md](bughunt/bughuntlog.md) for the bug-hunt protocol.

---

## Bugs

Confirmed defects found by code inspection. Each has a specific file and line reference.

- **`start_new_session=True` is a no-op on Windows in `index-refresh.py`** — `subprocess.Popen(..., start_new_session=True)` is documented as POSIX-only; on Windows the kwarg is ignored and the child remains attached to the parent, defeating the detach intent. Fix: branch on `sys.platform`; on Windows pass `creationflags=subprocess.DETACHED_PROCESS` (or `CREATE_NEW_PROCESS_GROUP`) instead. (`hooks/index-refresh.py:72`)

- **Venv path containing `"` produces invalid Python in the printed `VENV_PY` line** — `f'       VENV_PY = _venv_python("{venv_dir}")'` interpolates the path raw; a path with an embedded `"` yields a `SyntaxError` when the user pastes it. Fix: emit `repr(str(venv_dir))` or `json.dumps(str(venv_dir))` so escaping is correct. (`install.py:189-190`)

- **`--source-type` argparse `choices` may drift from values actually stored in `documents.source_type`** — argparse rejects valid values present in older databases (or accepts values no longer produced) because the choices list and the column are two unsynchronised sources of truth. Fix: derive choices from `SELECT DISTINCT source_type FROM documents` at runtime, or add a `CHECK` constraint to `index.sql` that pins the vocabulary. (`tools/search.py:70`)

- **Vectors stored in native byte order — `index.db` is not portable across endianness** — `np.float32.tobytes()` writes host-native bytes; `np.frombuffer(..., dtype=np.float32)` reads with the host's endianness. A db built on little-endian and read on big-endian (POWER, s390x, some embedded ARM) returns silently wrong cosine scores. Fix: pin dtype to `<f4` (little-endian) on both write and read paths. (`tools/embeddings.py:296`, `tools/search.py:46`)

- **`enumerate_sources()` aborts the entire refresh on a single permission-denied directory** — `path.rglob("*")` propagates `PermissionError` from a single unreadable subtree, killing the run and leaving the index stale. Fix: wrap each per-source enumeration in `try/except OSError`, log a warning, and continue. (`tools/embeddings.py:173`)

- **Heading-dedup `_2` suffix can collide with a literal `## Foo_2` in the same file** — the dedup logic renames repeats to `Foo_2`, but if the source already contains `## Foo_2` literally, both end up with identical `(source_path, source_key)` and the UPSERT silently overwrites. Fix: pre-scan all heading keys for the file and only suffix when the candidate is free, or use an ordinal scheme (`Foo#2`) using a character that cannot appear in a markdown heading. (`tools/embeddings.py:94-99`)

- **Installer copies files before the venv check, leaving a silent half-install on abort** — Step 1 copies `tools/`, `schema/`, and `.claude/hooks/` into the target *before* `detect_venv()` runs in Step 2; when no venv is found the installer prints an error and `return 1`, but the already-copied files remain and Step 5 `settings.json` wiring never runs. The hooks are deployed but never registered with Claude Code, so the toolkit is silently inert and a casual user sees files appear and assumes success. Fix: resolve/validate the venv (Step 2) *before* any file copy (Step 1), or roll back copied files on a pre-wiring abort, or decouple `settings.json` wiring so a later re-run completes the install. (`install.py:607-621`, `install.py:626-639`, `install.py:683-688`)

- **`search-first.py` gates `.md` files under `INDEXED_SOURCE_DIRS` that `embeddings.py` never indexes** — `is_indexed()` returns `rel.endswith((".py", ".sql", ".md"))` for any path under an `INDEXED_SOURCE_DIRS` entry (`hooks/search-first.py:58-59`), but `enumerate_sources()` only collects `*.py` and `*.sql` from those dirs — never `*.md` (`tools/embeddings.py:194-211`). Adding a directory to `INDEXED_SOURCE_DIRS` therefore makes the search-first hook block Reads of `.md` files in it even though they are absent from `index.db`, and a search scoped to them returns nothing — the user can only clear the gate with an unrelated search. Fix: either index `.md` from `INDEXED_SOURCE_DIRS` in `enumerate_sources()`, or drop `.md` from the `INDEXED_SOURCE_DIRS` branch of `is_indexed()` so the gate matches what is actually indexed. (`hooks/search-first.py:58-59`, `tools/embeddings.py:194-211`)

- **`search-first.py` docstring says hooks are wired into `settings.local.json`, but the installer writes `settings.json`** — `hooks/search-first.py:6` states "install.py wires this into .claude/settings.local.json automatically", while `install.py:1004` deliberately wires hooks into the project-shared `.claude/settings.json` (so Claude rewrites can't clobber them). The stale docstring misleads anyone debugging why the gate isn't firing. Fix: correct the docstring to `settings.json`. (`hooks/search-first.py:6`)

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
- **Implement graceful degradation** — explicit handlers in `tools/embeddings.py` and `tools/search.py` for each failure condition; each catches the failure, emits a structured warning to stderr, and continues rather than propagating an exception.
- **`AGENT_MODEL` config variable** — add an optional `AGENT_MODEL` string to `search_config.py` (e.g. `"claude-sonnet-4-6"`). When set, `search.py` uses a lookup table to select default `k` and warn if chunks risk filling the window. When unset, current defaults apply unchanged.
- **Context-window lookup table** — ship `tools/model_profiles.py` mapping Claude model IDs (Haiku / Sonnet / Opus) to context window size and recommended `k` / `MAX_CHUNK_CHARS` values.

### Low Priority

- **Remote index option** — store `index.db` in S3 / R2 for teams sharing an index across machines
- **`search.py` interactive REPL** — `search.py --interactive` for rapid exploratory querying during development
- **`embeddings.py` file-watcher mode** — a `watch` subcommand using `watchdog` that monitors `INDEXED_SOURCE_DIRS` and triggers incremental refresh automatically on save, as an alternative to the PostToolUse hook

---

## Installer

### High Priority

- **Auto-patch `INDEXED_SOURCE_DIRS` in `search_config.py`** — `VENV_PY` is now auto-patched after venv detection (`install.py:955`), but `INDEXED_SOURCE_DIRS` is left at the less_tokens defaults (`tools/`, `schema/`), not the host's source dirs. Scan the host repo for directories containing `.py` files and patch in place (or prompt with the discovered list). The next-steps output should also explain the `INDEXED_SOURCE_DIRS` (`.py`/`.sql`) vs `INDEXED_ROOT_GLOBS` (`.md`) split so users of non-Python repos know which variable to edit.
- **Auto-create a venv when none is detected** — with no venv present the installer exits having written nothing, printing the exact `python3 -m venv .venv` command the user must run before re-invoking the installer. Add a `--create-venv` flag (or interactive `No venv found. Create .venv-tokens now? [Y/n]`) that creates `.venv-tokens` (already the preferred isolation name) and proceeds in a single pass.
- **Recursive-glob guidance for doc-heavy repos** — `INDEXED_ROOT_GLOBS` defaults to `("*.md",)` evaluated via non-recursive `BASE.glob` (`tools/embeddings.py:180`), so a repo whose docs live in `docs/`, `.agents/`, etc. indexes none of them. `pathlib` does support `**`, but nothing tells the user. Add a `# supports recursive patterns, e.g. "docs/**/*.md"` comment in `search_config.py`, surface `INDEXED_ROOT_GLOBS` in the next-steps output, and if the installer finds no `.py` files but many subdirectory `.md` files, suggest recursive globs.
- **Choose hooks target: `settings.json` vs `settings.local.json`** — the installer always wires hooks into the committed `.claude/settings.json` (`install.py:1004`); the rationale (Claude can clobber `settings.local.json`) is sound, but it silently edits a project-shared, sometimes change-controlled file. Add a `--local` flag (and/or interactive `Install hooks for the team (settings.json) or just you (settings.local.json)? [team/me]`); when writing to a pre-existing non-empty `settings.json`, print a one-line notice that a committed file is being modified.
- **`install.py --update`** — re-copy hook and tool files without touching `search_config.py` or `index.db` (safe upgrade path)
- **`install.py --check`** — verify that a previous install is still valid: venv exists, fastembed is installed, `index.db` is present and has ≥1 row, `VENV_PY` resolves to a real interpreter, `.claude/hooks/*.py` exist and are executable, hooks are wired in `.claude/settings.json` (the file the installer actually writes — `install.py:1004`), and a `tools/search.py "test"` smoke query returns without error. Print `[✓]`/`[✗]` per check and exit non-zero with a specific message for each failure.
- **`VIRTUAL_ENV` environment variable fallback in venv detection** — `detect_venv()` in `install.py` and `_venv_python()` in `search_config.py` should check the `VIRTUAL_ENV` env var first, since it's set by `activate` and reliably points to the active venv on all platforms
- **`install.py --dry-run`** — print the resolved target root, every file that would be copied (with new/skip/overwrite status), venv detection result, `search_config.py` variables that would be injected, and the `settings.json` hooks that would be wired — all without writing anything. There is currently no way to preview the blast radius on the host project before mutating it. (no `--dry-run` in arg parser, `install.py:528-557`)
- **Namespace-collision management for copied trees** — the installer copies into bare `tools/`, `schema/`, and `.claude/hooks/` at the host root; a host project with its own `tools/` or `schema/` directory gets less_tokens files merged into it (and host files can be clobbered with `--overwrite-modified`), risking shadowed imports. Detect pre-existing host paths that aren't from a prior less_tokens install and warn, or support an install prefix / dedicated subdir, before copying. (`install.py:607-621`)

### Medium Priority

- **Build the index during install by default** — the `--build` flag exists (`install.py:823`, runs `build_index`) and is documented, but a default install leaves no `index.db`, so `tools/search.py` returns empty until the user runs the build manually (the first run also downloads the fastembed model). Make the build run by default with an opt-out, or interactively prompt `Build the index now? ~30s on first run (model download). [Y/n]` — so the install completes in one step instead of two.
- **`install.py --uninstall`** — reverse a deployment: remove the copied `tools/`, `schema/`, and `.claude/hooks/` files, strip the less_tokens hook entries from `.claude/settings.json`, and optionally drop `index.db` — leaving host-authored files untouched. The only cleanup path today is a manual `rm -rf`, which is error-prone next to host files (see namespace-collision item) and leaves orphaned `settings.json` hook entries pointing at deleted scripts.
- **Offer to gitignore deployed files (host-repo git pollution)** — the copied trees land untracked in the host project's git repo and pollute `git status` (a host `.gitignore` typically ignores only the `less_tokens/` clone, not the deployed `tools/`, `schema/`, `.claude/hooks/`, `index.db`, `.claude/state/`). After copying, offer to append these paths to the host `.gitignore`, or document explicitly that they should be committed — make the choice deliberate rather than silent. A `--gitignore` flag and a one-time re-run tip already exist (`install.py:837`, `install.py:665`); the remaining gap is that the step stays opt-in — make it default-on with an opt-out (or interactive `[Y/n]` defaulting to yes) so `index.db`, `.claude/state/`, and the venv never silently pollute `git status`.

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
- **Dashboard command** — `embeddings.py stats --verbose` showing index age, chunk count by source type, and estimated coverage

---

## Developer Experience

### Medium Priority

- **Consider GitHub self-hosted runners for the perf job** — the `perf` CI job downloads the fastembed model (~130 MB `BAAI/bge-small-en-v1.5`) and relies on `actions/cache` for subsequent runs; a cold cache miss adds significant wall-clock time and introduces network variance into timing results. A self-hosted runner with the model pre-installed in `~/.cache/huggingface` would eliminate both the download and the cache-restore step, and would provide stable CPU baselines so reduction-percentage regressions aren't masked by runner noise. Trade-off: self-hosted runners require infrastructure maintenance and the runner must be registered to the repo; only worth the overhead if perf run times become a bottleneck or timing variance starts producing false failures.
- **`pre-commit` config** — add `ruff` and `pyright` hooks so contributors get linting feedback before pushing

---

## Proposed Strategies

### Strategy 6 — Tiered Effort

Route each task to the cheapest Claude model + effort level it needs. Three tiers: **L1 Mechanical** (Haiku, one confirmation, no summaries), **L2 Rules** (Sonnet, result + brief reasoning), **L3 Planning** (Opus, full analysis). Before each task the agent emits one line with the recommended tier only when it changes from the prior turn. Implementation: `caveman/tier-matrix.md` appended to `CLAUDE.md` + `AGENT_TIER_HINTS: bool` config flag. Expected savings: 50–70% blended reduction.

### Strategy 4 — Prompt Caching *(deferred — likely redundant with Claude Code defaults)*

Claude Code already caches the system prompt and `CLAUDE.md` automatically. Revisit if measurement on a real session shows the auto-cache is missing large doc files Claude reads every turn.
