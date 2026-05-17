# Continue — atomic backlog bugfix session

Handoff doc for resuming the `/bugfix` loop on `less_tokens`. Updated 2026-05-16.

## Context

Working through `BACKLOG.md` → `## Bugs` one at a time with the **bugfix** skill
(test-driven, one atomic commit per bug: failing test → minimal fix → ruff →
CHANGELOG → delete backlog item → commit). The user confirms each bug before the
next ("fix next backlog" → "yes" → "continue"); do **not** auto-loop the whole list.

Branch: `install/lifecycle-flags`. **Commits are local — not pushed.**
Memory rule: always open a PR, never push to `main` directly (main is protected).

### Fixed this session (3 commits, local)

| Commit | Bug |
|---|---|
| `c165048` | `index-refresh.py` Windows detach — `start_new_session` is POSIX-only; added `_detach_kwargs(platform)` (creationflags on win32) |
| `6423735` | `install.py` venv path with `"`/`\` wrote invalid `search_config.py`; added shared `_venv_python_call()` (json.dumps) |
| `fe51695` | `search.py --source-type` choices drifted from the index; added `_source_type_choices()` (SELECT DISTINCT at runtime) |

## Environment / project gotchas (learned this session)

- **No venv here.** Run tests with system `python3 -m pytest` (pytest 8.4.2, Python 3.9.6).
- **ruff**: `/opt/homebrew/bin/ruff`. **mypy is NOT installed** and the project ships
  no mypy config → type-check step is unavailable; note that in the report, don't block on it.
- Tests: `tests/unit/` (fast, no fastembed), `tests/integration/test_install.py`,
  `tests/perf/` (marked `perf`, skipped locally). pyproject sets `pythonpath=["."]`.
  Hooks load via `tests.conftest.load_hook`; `search.py` imports the **top-level** `db`
  module (tools/ on sys.path) — patch `INDEX_DB` on `sys.modules[search.connect_index.__module__]`.
- **Backlog/changelog lifecycle** (CLAUDE.md): add an entry under `[Unreleased]` in
  `CHANGELOG.md` (first `### Fixed` block, user-perspective, Keep a Changelog) **and
  delete the backlog item entirely** — no strike-through / no DONE marker.
- If the fixed bug is also listed in **CLAUDE.md → "Known bugs worth avoiding"**,
  remove that line too (did this for `c165048`; the next bug IS listed there).
- Commit trailer: `Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>`
  (accurate model — overrides the skill template's Sonnet 4.6).
- Commit only; **do not push**. Keep commits atomic (fix + test + CHANGELOG +
  BACKLOG, ~4-5 coupled files). Minimal scope — no "while we're here" refactors.
- Known pre-existing debt, intentionally **out of scope**: 7 `F541` (empty
  f-strings) in untouched regions of `install.py`. Don't fix as part of a bug.

## Next steps — remaining `## Bugs`, in order

### 1. NEXT — `enumerate_sources()` aborts refresh on one permission-denied dir
`path.rglob("*")` propagates `PermissionError`, killing the whole run.
Fix: wrap each per-source enumeration in `try/except OSError`, warn, continue.
(`tools/embeddings.py:173`)

### 2. Heading-dedup `_2` suffix collides with literal `## Foo_2`
UPSERT silently overwrites when a real `## Foo_2` exists alongside a deduped one.
Fix: pre-scan heading keys and only suffix when free, or ordinal scheme with a
char illegal in markdown headings. (`tools/embeddings.py:94-99`)

### 3. `search-first.py` docstring says `settings.local.json`
Installer writes `settings.json` (`install.py:1004`). Stale docstring at
`hooks/search-first.py:6`. Trivial doc fix (still write a test if practical).

## Resume commands

```bash
# from /Users/michael/Documents/GitHub/flying_buttress/less_tokens
git status --short && git log --oneline main..HEAD   # confirm clean + 3 commits
python3 -m pytest -q                                  # baseline (expect ~137 passed, 1 skipped)
# then invoke the bugfix skill / "continue" for bug #1 above
```

When all `## Bugs` are cleared, open a PR for `install/lifecycle-flags`
(do not push to main). Delete this file once the loop is finished.
