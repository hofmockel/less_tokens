---
name: agentsmd
description: >-
  Prune AGENTS.md to only what Codex must always load. Use when AGENTS.md grows
  large, the agentsmd-budget hook fires, or before a release. Moves searchable
  detail to indexed docs and fixes stale references.
---

# agentsmd — keep AGENTS.md lean

AGENTS.md is always-loaded Codex context. Every token is paid before task details arrive. Keep only standing instructions Codex needs before acting. Move discoverable detail to indexed docs.

## Keep / Cut Rubric

Ask: **could `.less_tokens/tools/search.py` find this during the task?**

- Yes -> move it to the overflow doc (`AGENTS_MD_OVERFLOW_DOC`, default `documentation.md`).
- No -> keep it as a standing rule.

Keep: agent rules, token-discipline defaults, mandatory commands, safety constraints, gotchas that break work if unknown upfront.

Move: architecture detail, long workflows, file maps, historical notes, duplicated README/BACKLOG/docs content, examples that search can recover.

Fix stale `path:line` refs. Prefer symbol names over line numbers.

## Procedure

1. Audit with code, not eyeballing:

   ```bash
   .less_tokens/bin/python .less_tokens/tools/agentsmd_audit.py
   ```

2. For each `CUT->doc` or `REVIEW`, move the content to the overflow doc and leave only a short pointer if the pointer is itself a standing rule.

3. For each `FIX-REF`, repair or remove the stale reference.

4. For each `TRIM`, rewrite directly and remove filler.

5. Re-audit strictly:

   ```bash
   .less_tokens/bin/python .less_tokens/tools/agentsmd_audit.py --strict
   ```

6. Verify recall for moved topics:

   ```bash
   .less_tokens/bin/python .less_tokens/tools/search.py "<moved topic>"
   ```

   If search cannot find the moved content, restore it or refresh the index first:

   ```bash
   .less_tokens/bin/python .less_tokens/tools/embeddings.py refresh
   ```

## Enforcement

`agents/codex/hooks/agentsmd-budget.py` blocks AGENTS.md edits that exceed budget or add stale refs. Installed Codex hooks run it after AGENTS.md writes.

## Config

`search_config.py`: `AGENTS_MD_TOKEN_BUDGET` (default 1200), `AGENTS_MD_OVERFLOW_DOC` (default `documentation.md`).
