# Continue: less_tokens

> **Next focus:** turn the additive HTML documentation plan into implementation, or pick the next BACKLOG.md item.

## Current state
`main` is clean and pushed at `781e2d9`. The latest work added `HTML_DOCUMENTATION_PLAN.md`, a detailed plan for an additive static HTML documentation layer. Existing Markdown docs are not to be replaced, removed, renamed, or shrunk; the HTML layer should link back to them and present richer visual/navigation/presentation material.

## What happened this session
- Created `HTML_DOCUMENTATION_PLAN.md` with information architecture, a ~25-slide presentation outline, strategy/scaffolding/reference page plans, diagrams, graph/data sources, hyperlinking rules, generator scripts, implementation phases, and acceptance criteria.
- Corrected the docs policy after clarification: the site is additive only. `README.md`, `DOCUMENTATION.md`, `DECISIONS.md`, `BACKLOG.md`, `CHANGELOG.md`, `AGENTS.md`, and `CLAUDE.md` stay in place.
- Committed and pushed `781e2d9 Add HTML documentation plan` to `main`. GitHub reported a bypassed expected `Analyze (Python)` status check, but push succeeded.

## Open work
See [BACKLOG.md](BACKLOG.md). For the docs effort, start from [HTML_DOCUMENTATION_PLAN.md](HTML_DOCUMENTATION_PLAN.md) and implement Phase 1 first: docs source tree, base styling, overview, presentation, architecture, and reference landing pages.

## Suggested skills
- `$less-tokens` — search and inspect the codebase without dumping large files.
- `$agentsmd` — keep agent-facing docs lean if touching `AGENTS.md` or instruction material.

## Start here
Read `HTML_DOCUMENTATION_PLAN.md`, then scaffold the additive `docs-site/` structure without modifying existing root Markdown docs.

---
_Last updated at HEAD `781e2d9` on 2026-07-15._
