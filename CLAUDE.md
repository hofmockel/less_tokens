# CLAUDE.md

Guidance for Claude Code in this repo. Architecture, internals, and the full install/verify walkthrough live in `DOCUMENTATION.md` — it is indexed, so search it instead of bloating this file.

## Output style

Terse, direct prose — no filler, no padding. Full spec: `.claude/rules/caveman.md`.

## Test commands

`.claude/.venv-tokens/bin/python .claude/tools/dev.py {unit|integration|all|single <nodeid>}`. Full install/verify walkthrough and CI matrix: `DOCUMENTATION.md`.

## Backlog and changelog lifecycle

Code-changing PRs need a `CHANGELOG.md` `[Unreleased]` entry — enforced by `changelog_gate.py` in pull-request CI, not on each commit. Also delete the shipped item from `BACKLOG.md` (no strike-through, no "DONE" marker); when the entry ships a backlog item, cite its ID (`- [P2] ...`) and the gate fails if that ID still has a heading in `BACKLOG.md`. A duplicate across README and BACKLOG is a bookkeeping bug.

## graphify

Knowledge graph at graphify-out/. For codebase questions run `graphify query "<question>"` (when graphify-out/graph.json exists); `graphify path "<A>" "<B>"` for relationships; `graphify explain "<concept>"` for focused concepts — each returns a scoped subgraph, smaller than raw grep. Use graphify-out/wiki/index.md for broad navigation; read GRAPH_REPORT.md only for broad architecture review. After code changes: `graphify update .` (AST-only, no API cost).
