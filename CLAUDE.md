# CLAUDE.md

Guidance for Claude Code in this repo. Architecture, internals, and the full install/verify walkthrough live in `DOCUMENTATION.md` — it is indexed, so search it instead of bloating this file.

## Output style

Use concise, direct prose. Avoid filler such as "certainly", "I'd be happy to", and "Great question". Do not add padding or a recap when the answer is already complete. Say what is needed, then stop.

Good: "File not found. Check path."
Bad: "I apologize, but I was unable to locate the file you specified."

Code blocks should stay idiomatic and readable. The full terse-output spec is in `.claude/rules/caveman.md`.

_Moved to DOCUMENTATION.md → Project purpose._
## Test commands

```bash
# Unit + integration (no fastembed needed — matches CI)
.claude/.venv-tokens/bin/python -m pip install numpy pytest
.claude/.venv-tokens/bin/python -m pytest .claude/tests/unit/ -v
.claude/.venv-tokens/bin/python -m pytest .claude/tests/integration/ -v
# Single test
.claude/.venv-tokens/bin/python -m pytest .claude/tests/unit/test_chunkers.py::<test_name> -v
```

pytest config is in `pyproject.toml`. CI runs unit + integration on Python 3.9/3.11/3.12 × 3 OS. Full install/verify walkthrough: `DOCUMENTATION.md`.

## Backlog and changelog lifecycle

Code-changing PRs need a `CHANGELOG.md` `[Unreleased]` entry — enforced by `changelog_gate.py` (CI + pre-commit). Also delete the shipped item from `BACKLOG.md` (no strike-through, no "DONE" marker); when the entry ships a backlog item, cite its ID (`- [P2] ...`) and the gate fails if that ID still has a heading in `BACKLOG.md`. A duplicate across README and BACKLOG is a bookkeeping bug.

## graphify

Knowledge graph at graphify-out/. For codebase questions run `graphify query "<question>"` (when graphify-out/graph.json exists); `graphify path "<A>" "<B>"` for relationships; `graphify explain "<concept>"` for focused concepts — each returns a scoped subgraph, smaller than raw grep. Use graphify-out/wiki/index.md for broad navigation; read GRAPH_REPORT.md only for broad architecture review. After code changes: `graphify update .` (AST-only, no API cost).
