# CLAUDE.md

Guidance for Claude Code in this repo. Architecture, internals, and the full install/verify walkthrough live in `DOCUMENTATION.md` — it is indexed, so search it instead of bloating this file.

## Output style — Caveman Mode

Talk like caveman. Short sentence. No filler. No "certainly", "I'd be happy to", "Great question". No padding. No summary at end. Noun, verb, skip article. Say what need saying. Stop.

Good: "File not found. Check path."
Bad: "I apologize, but I was unable to locate the file you specified."

Code blocks stay normal — only prose go caveman. Full spec: `.claude/rules/caveman.md`.

## Project purpose

A **toolkit** whose job is to be installed *into other projects*: `install.py` targets a host project's parent dir and deploys `.claude/` (tools, hooks, schema, venv, `index.db`); re-run after `git pull` to upgrade in place. That is the primary mission.

But it is also developed **and dogfooded here** — this repo runs its own hooks, search, and skills to spend fewer tokens while building less_tokens. When working in this repo, use the installed tooling (search before Read, the skills, the budget hooks), not just edit it. Strategies: vector search, caveman mode, tool-output truncation, session compaction. Deploy mechanics: `DOCUMENTATION.md`.

## Test commands

```bash
# Unit + integration (no fastembed needed — matches CI)
.claude/.venv-tokens/bin/python -m pip install numpy pytest
.claude/.venv-tokens/bin/python -m pytest .claude/tests/unit/ -v
.claude/.venv-tokens/bin/python -m pytest .claude/tests/integration/ -v
# Single test
.claude/.venv-tokens/bin/python -m pytest .claude/tests/unit/test_chunkers.py::<test_name> -v
# Perf (needs fastembed; marker-gated, ubuntu CI only)
.claude/.venv-tokens/bin/python -m pytest .claude/tests/perf/ -v -m perf
```

pytest config is in `pyproject.toml`. CI runs unit + integration on Python 3.9/3.11/3.12 × 3 OS. Full install/verify walkthrough: `DOCUMENTATION.md`.

## Backlog and changelog lifecycle

Code-changing PRs need a `CHANGELOG.md` `[Unreleased]` entry — enforced by `changelog_gate.py` (CI + pre-commit). Also delete the shipped item from `BACKLOG.md` (no strike-through, no "DONE" marker); when the entry ships a backlog item, cite its ID (`- [P2] ...`) and the gate fails if that ID still has a heading in `BACKLOG.md`. A duplicate across README and BACKLOG is a bookkeeping bug.

## graphify

Knowledge graph at graphify-out/. For codebase questions run `graphify query "<question>"` (when graphify-out/graph.json exists); `graphify path "<A>" "<B>"` for relationships; `graphify explain "<concept>"` for focused concepts — each returns a scoped subgraph, smaller than raw grep. Use graphify-out/wiki/index.md for broad navigation; read GRAPH_REPORT.md only for broad architecture review. After code changes: `graphify update .` (AST-only, no API cost).
