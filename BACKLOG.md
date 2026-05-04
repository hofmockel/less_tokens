# Backlog

## Purpose

This file is the single source of truth for planned work — new features, bug fixes, and improvements that have been identified but not yet started. It exists so that anyone (contributor, maintainer, or user) can see what's coming, understand priorities, and avoid duplicating effort.

## How to use it

**Reporting a bug or requesting a feature?**
Open a [GitHub Issue](../../issues) using the appropriate template. If the maintainer accepts it, it will be added here.

**Picking up work?**
Choose an item from High Priority, assign yourself in the corresponding Issue, and open a PR when ready. See [CONTRIBUTING.md](CONTRIBUTING.md) for the full workflow.

**When work ships:**
Remove the item from this file and add an entry to [CHANGELOG.md](CHANGELOG.md) under `[Unreleased]`.

**Priority definitions:**

| Level | Meaning |
|---|---|
| **High** | Clear value, known implementation path — good first targets |
| **Medium** | Important but less urgent; may need more design thought |
| **Low / Ideas** | Worth tracking, no commitment to timeline |

---

## High Priority

### Vector Search

- **Multi-repo indexing** — support indexing across multiple project roots so a single search spans related repos (monorepo support)
- **Stale index warning** — detect when indexed files have changed since last refresh and surface a warning in `search.py` output before results
- **Configurable chunk size** — expose `MAX_CHUNK_CHARS` in `search_config.py` so users can tune for their model's context window
- **TypeScript / JavaScript chunking** — add a `chunk_js` strategy (function-level, like `chunk_python`) for projects with `.ts` / `.js` source

### Caveman Mode

- **Calibrated verbosity levels** — replace binary caveman on/off with a 1–5 verbosity dial in `search_config.py`; level 1 = full caveman, level 5 = normal prose
- **Per-task exemptions** — allow CLAUDE.md to declare specific task types (e.g., user-facing copy, PR descriptions) that bypass caveman mode

### Installer

- **Auto-update `search_config.py`** — after detecting the venv, patch `VENV_PY` and `INDEXED_SOURCE_DIRS` in place rather than just printing the line
- **`install.py --update`** — re-copy hook and tool files without touching `search_config.py` or `index.db` (safe upgrade path)

---

## Medium Priority

### Observability

- **Search quality metrics** — log query, top result score, and result count to `.claude/state/search.log` so users can audit what Claude is finding
- **Token savings estimate** — after each search, print an estimated token delta vs. reading all matched files in full
- **Dashboard command** — `embeddings.py stats --verbose` showing index age, chunk count by source type, and estimated coverage

### Developer Experience

- **`pytest` test suite** — unit tests for `chunk_python`, `chunk_markdown`, `is_indexed`, and the incremental refresh hash logic
- **CI: test on Python 3.9 / 3.11 / 3.12** — GitHub Actions matrix to catch version regressions early
- **`pre-commit` config** — add `ruff` and `pyright` hooks so contributors get linting feedback before pushing

### Documentation

- **Animated GIF demo** — screencast showing a before/after: full Read vs. search returning targeted chunks
- **"Porting guide" doc** — step-by-step walkthrough of adapting `search_config.py` for a new project type (Django, Next.js, Rust)
- **Token savings benchmarks** — documented measurements on a real codebase showing actual input/output token reduction

---

## Low Priority / Ideas

- **Embeddings model swap** — make the model name configurable in `search_config.py`; document the dimension change requirement
- **Remote index option** — store `index.db` in S3 / R2 for teams sharing an index across machines
- **VS Code extension** — surface `search.py` results in the editor sidebar as a complement to the Claude Code hook
- **`search.py` interactive REPL** — `search.py --interactive` for rapid exploratory querying during development
- **Automatic `INDEXED_SOURCE_DIRS` detection** — inspect the repo and suggest dirs based on file type distribution
