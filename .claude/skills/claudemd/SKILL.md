---
name: claudemd
description: >-
  Prune CLAUDE.md to its always-loaded essentials; move detail to indexed docs,
  fix stale refs. Use when CLAUDE.md grows large, the claudemd-budget hook fires,
  or before a release.
---

# claudemd — keep CLAUDE.md lean

CLAUDE.md inject every turn. Never searched. Every token = per-turn tax. Keep only what must be in context before Claude acts. Push the rest to an indexed doc — search find it when needed.

## Keep / cut rubric

Test each section: **could `search.py` surface this mid-task in one query?**

- Yes → discoverable. **CUT** to the overflow doc (`CLAUDE_MD_OVERFLOW_DOC`, default `DOCUMENTATION.md`).
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

2. Move + re-audit + verify recall for every `CUT→doc`/`REVIEW` section in one command:

   ```bash
   python .claude/tools/instruction_prune.py --agent claude                      # dry run: shows the plan
   python .claude/tools/instruction_prune.py --agent claude --apply --verify-recall
   ```

   `--apply` appends each section to the overflow doc and leaves a one-line pointer at its old spot (delete the pointer by hand later if the section wasn't actually a standing rule; skip it entirely with `--no-pointer`). `--verify-recall` searches for each moved topic afterward and prints PASS/FAIL. **Safety rule: if verify-recall reports FAIL for a topic, restore that section to CLAUDE.md by hand** — the tool never auto-restores, since a FAIL means the content isn't reachable by the mechanism that justified cutting it, and auto-restoring risks clobbering a concurrent edit.

3. For each `FIX-REF` the dry run lists: repair or drop by hand. Prefer symbol names over line numbers — line numbers rot, names don't.

4. For each `TRIM` the dry run lists: rewrite caveman by hand (see `.claude/rules/caveman.md`). Rewriting prose is a judgment call the tool doesn't attempt.

## Enforcement

`.claude/hooks/claudemd-budget.py` (PostToolUse on Edit/Write/MultiEdit) blocks when CLAUDE.md goes over budget or gains a dead ref. Budget set in `search_config.py` (`CLAUDE_MD_TOKEN_BUDGET`, 0 disables).

## Wider always-loaded surfaces

The same audit covers other surfaces injected every turn:

```bash
python .claude/tools/claudemd_audit.py --rules    # .claude/rules/*.md, per-file token budget
python .claude/tools/claudemd_audit.py --skills   # SKILL.md descriptions: word cap + overlap
```

`--skills` flags descriptions over the word cap, missing descriptions (skill won't trigger), and near-duplicate descriptions that compete to trigger (needs fastembed; overlap check skips gracefully without it).

## Root-doc canonical homes

Root docs overlap too — same topic copied across README, DOCUMENTATION.md, CONTRIBUTING.md, CLAUDE.md, `.claude/rules/*.md`. Each topic gets one canonical home; the rest reduce to a one-line pointer. When pruning or before a release, check these and fix drift:

| Topic | Canonical | Others point here |
|---|---|---|
| Repo layout tree | DOCUMENTATION.md → Repository layout | README |
| Install / config / usage / hook wiring | DOCUMENTATION.md | README (teaser only) |
| Contributing | CONTRIBUTING.md | README, DOCUMENTATION.md |
| License | README + `LICENSE` | DOCUMENTATION.md |
| Caveman / terse-output spec | `.claude/rules/caveman.md` | CLAUDE.md, DOCUMENTATION.md |
| Token-reduction strategy | DOCUMENTATION.md | BACKLOG.md |

A topic duplicated across two root docs is a bookkeeping bug — collapse the non-canonical copy to a pointer.

## Config

`search_config.py`: `CLAUDE_MD_TOKEN_BUDGET` (default 1200), `CLAUDE_MD_OVERFLOW_DOC` (default `DOCUMENTATION.md`), `RULES_TOKEN_BUDGET` (default 600), `SKILL_DESC_WORD_CAP` (default 50), `SKILL_DESC_DUP_SIM` (default 0.85).
