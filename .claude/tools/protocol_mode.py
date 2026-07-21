#!/usr/bin/env python3
"""Shared mode-detection heuristic for bug-hunt-protocol.md and bugfix-protocol.md.

Both protocols run against an arbitrary target repo and must first decide whether
it is in "docs mode" (interlinked Markdown specs, no test suite — a bug is a
cross-document inconsistency) or "code mode" (application code with a runnable
test suite — a bug is a logic/state/silent-failure error).

This heuristic is the ONE place that decision is spelled out. bug_hunt_docs.py and
bugfix_docs.py both render it into their respective protocol docs verbatim, so the
two protocols can never drift on what "docs mode" vs "code mode" means — the same
class of bug this repo's own docs-mode branch exists to catch, so it would be a bit
rich to let it happen here via hand-copied prose.

Why this lives outside bug_hunt_registry.py: SEVERITY_TIERS / TARGET_FILES /
PROMPT_TEMPLATE in that file are less_tokens' own code-mode defaults (they answer
"what does a hunt against *this* repo look like") and stay registry-driven because
this repo genuinely has a target-file list to regenerate from. Mode detection isn't
a per-repo default — it's the same check regardless of which repo the skill is
copied into — so it gets its own tiny shared module instead of living inside a
registry named after one half of the decision.
"""

from __future__ import annotations

MODE_HEURISTIC = """\
Run against $REPO_ROOT (from `git rev-parse --show-toplevel`), in order, first match wins:

1. **Test runner detected -> code mode.** Any of: `pytest.ini`; `pyproject.toml` with a
   `[tool.pytest.ini_options]` table; `setup.cfg` with `[tool:pytest]`; `package.json` with a
   `test` script invoking `jest`/`mocha`/`vitest`/`ava`; a `Makefile`/`justfile` `test` target; or
   a `tests/`/`test/` directory containing `test_*.py`, `*_test.py`, `*.test.js`, or `*.spec.ts`
   files.
2. **No test runner, but `BACKLOG.md` or `backlog.md` exists and Markdown specs dominate ->
   docs mode.** Rough signal for "Markdown specs dominate": more tracked `*.md` files than
   source files at the repo root, or no conventional source directory (`src/`, `lib/`, `app/`,
   or the language-equivalent).
3. **Neither condition matches -> ambiguous.** Do not guess. State what was checked and ask the
   user which mode applies before running either protocol.

This is a heuristic, not a certainty. Print which branch fired and why as the first line of any
hunt/fix output.
"""
