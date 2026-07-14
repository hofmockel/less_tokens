---
name: agentsmd
description: >-
  Prune AGENTS.md to Codex's always-load essentials; move detail to indexed docs,
  fix stale refs. Use when AGENTS.md grows large, the agentsmd-budget hook fires,
  or before a release.
---

# agentsmd — keep AGENTS.md lean

AGENTS.md is always-loaded Codex context. Every token is paid before task details arrive. Keep only standing instructions Codex needs before acting. Move discoverable detail to indexed docs.

## Keep / Cut Rubric

Ask: **could `.less_tokens/tools/search.py` find this during the task?**

- Yes -> move it to the overflow doc (`AGENTS_MD_OVERFLOW_DOC`, default `DOCUMENTATION.md`).
- No -> keep it as a standing rule.

Keep: agent rules, token-discipline defaults, mandatory commands, safety constraints, gotchas that break work if unknown upfront.

Move: architecture detail, long workflows, file maps, historical notes, duplicated README/BACKLOG/docs content, examples that search can recover.

Fix stale `path:line` refs. Prefer symbol names over line numbers.

## Procedure

1. Audit with code, not eyeballing:

   ```bash
   .less_tokens/bin/python .less_tokens/tools/agentsmd_audit.py
   ```

2. Move + re-audit + verify recall for every `CUT->doc`/`REVIEW` section in one command:

   ```bash
   .less_tokens/bin/python .less_tokens/tools/instruction_prune.py --agent codex
   .less_tokens/bin/python .less_tokens/tools/instruction_prune.py --agent codex --apply --verify-recall
   ```

   `--apply` appends each section to the overflow doc and leaves a one-line pointer at its old spot (delete it by hand if the section wasn't a standing rule; skip it entirely with `--no-pointer`). `--verify-recall` searches for each moved topic and prints PASS/FAIL. Safety rule: if verify-recall FAILs, restore that section to AGENTS.md by hand -- the tool never auto-restores.

3. For each `FIX-REF` the dry run lists, repair or remove the stale reference by hand.

4. For each `TRIM` the dry run lists, rewrite directly and remove filler by hand.

## Enforcement

`agents/codex/hooks/agentsmd-budget.py` blocks AGENTS.md edits that exceed budget or add stale refs. Installed Codex hooks run it after AGENTS.md writes.

## Config

`search_config.py`: `AGENTS_MD_TOKEN_BUDGET` (default 1200), `AGENTS_MD_OVERFLOW_DOC` (default `DOCUMENTATION.md`).
