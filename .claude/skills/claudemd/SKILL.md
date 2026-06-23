---
name: claudemd
description: >-
  Prune CLAUDE.md to only what must be always-loaded. Use when CLAUDE.md grows
  large, the claudemd-budget hook fires, or before a release. Moves discoverable
  detail to an indexed doc and fixes stale references.
---

# claudemd — keep CLAUDE.md lean

CLAUDE.md inject every turn. Never searched. Every token = per-turn tax. Keep only what must be in context before Claude acts. Push the rest to an indexed doc — search find it when needed.

## Keep / cut rubric

Test each section: **could `search.py` surface this mid-task in one query?**

- Yes → discoverable. **CUT** to the overflow doc (`CLAUDE_MD_OVERFLOW_DOC`, default `documentation.md`).
- No → it's a standing rule, not a lookup. **KEEP**.

KEEP: output-style overrides (caveman), hard rules ("search before Read", `pip --break-system-packages`), gotchas that cause errors if unknown upfront, constant commands (test, build-index, search), default-overriding behavior.

CUT→doc: architecture deep-dives, layer splits, file-by-file tables, chunking/schema detail, history, anything duplicated in README/BACKLOG/docs.

FIX: stale `path:line` refs. TRIM: filler + long sentences → caveman.

## Procedure

1. Audit. Code measures; you don't eyeball.

   ```bash
   python .claude/tools/claudemd_audit.py
   ```

   Reports per-section tokens, a verdict (`KEEP / CUT→doc / TRIM / REVIEW`), stale refs (`FIX-REF`), and total vs budget. With a built index it adds a duplication % per section; without one it falls back to size-based `REVIEW`.

2. For each `CUT→doc` / `REVIEW`: append the section to the overflow doc (it is indexed), then delete from CLAUDE.md. Leave a one-line pointer only if it's a standing rule.

3. For each `FIX-REF`: repair or drop. Prefer symbol names over line numbers — line numbers rot, names don't.

4. For each `TRIM`: rewrite caveman (see `.claude/rules/caveman.md`).

5. Re-audit. Confirm under budget:

   ```bash
   python .claude/tools/claudemd_audit.py --strict   # exit 1 if over budget or dead refs
   ```

6. **Verify recall** — the safety net. For each moved section, search for its topic:

   ```bash
   .claude/.venv-tokens/bin/python .claude/tools/search.py "<moved topic>"
   ```

   If it does not come back, the cut was unsafe — restore it to CLAUDE.md. "Cut" only holds if the content is still reachable by the mechanism that justified cutting it. If the overflow doc isn't indexed yet, run `embeddings.py refresh` first.

## Enforcement

`.claude/hooks/claudemd-budget.py` (PostToolUse on Edit/Write/MultiEdit) blocks when CLAUDE.md goes over budget or gains a dead ref. Budget set in `search_config.py` (`CLAUDE_MD_TOKEN_BUDGET`, 0 disables).

## Wider always-loaded surfaces

The same audit covers other surfaces injected every turn:

```bash
python .claude/tools/claudemd_audit.py --rules    # .claude/rules/*.md, per-file token budget
python .claude/tools/claudemd_audit.py --skills   # SKILL.md descriptions: word cap + overlap
```

`--skills` flags descriptions over the word cap, missing descriptions (skill won't trigger), and near-duplicate descriptions that compete to trigger (needs fastembed; overlap check skips gracefully without it).

## Config

`search_config.py`: `CLAUDE_MD_TOKEN_BUDGET` (default 1200), `CLAUDE_MD_OVERFLOW_DOC` (default `documentation.md`), `RULES_TOKEN_BUDGET` (default 600), `SKILL_DESC_WORD_CAP` (default 50), `SKILL_DESC_DUP_SIM` (default 0.85).
