# claudemd.md — Proposal: a CLAUDE.md pruning skill

Goal: keep CLAUDE.md to **only what must be always-loaded**. Everything else moves to indexed docs Claude finds by search.

## Why this is on-mission

The whole repo says "search before Read" — pay tokens only for what you need, when you need it. CLAUDE.md is the **one file that breaks that rule**. It is injected into context every session, every turn. Never searched. Always paid.

So CLAUDE.md is the highest-tax file in the project. A 400-line CLAUDE.md is a 400-line tax on every single turn. Pruning it is the purest input-token win there is — and right now nothing guards it.

This repo's own CLAUDE.md shows the rot: deep architecture sections, file-by-file tables, and dozens of `install.py:566` / `install.py:1069-1070` line refs that go stale the moment someone edits `install.py`. Most of that is discoverable by search (`documentation.md`, source, BACKLOG are all indexed). It does not need to be always-loaded.

## Keep / cut rubric

**KEEP** (must be in context before the agent acts — cannot be discovered at the right moment):

- Output-style overrides (caveman).
- Hard rules / invariants: "search before Read", "pip needs `--break-system-packages`".
- Gotchas that cause errors if unknown upfront (the "known bugs to avoid" lines).
- Commands the agent runs constantly (test, build-index, search).
- Behavior that overrides Claude defaults.

**CUT → move to an indexed doc** (still findable by search, just not always-loaded):

- Architecture deep-dives, layer splits, file-by-file tables → `documentation.md` (already indexed).
- Chunking-strategy tables, schema detail.
- Historical / changelog-ish prose.
- Anything duplicated in README / BACKLOG / docs.

**FIX**:

- Stale `path:line` refs — dead path or out-of-range line.
- Verbose prose — collapse to caveman.

Test for KEEP vs CUT: *"If Claude needed this mid-task, could `search.py` surface it in one query?"* If yes → cut, it's discoverable. If no (it's a standing rule, not a lookup) → keep.

## Code over reasoning: the audit tool

Don't make Claude eyeball "is this too long." Measure it. `tools/claudemd_audit.py`:

1. **Token count per section** (split on headings) and total vs budget.
2. **Duplication check** — embed each section, cosine-compare against `index.db`. High similarity to already-indexed content = "discoverable elsewhere, cut." This reuses the existing embedding stack — the index already knows what's searchable.
3. **Stale refs** — parse `file:line` and bare paths; check the file exists and the line is in range. Flag dead ones.
4. **Verbosity** — reuse `VERBOSE_PATTERNS` from `caveman-reminder.py`; flag filler and long sentences.

Output is a verdict per section: `KEEP / CUT→doc / FIX-REF / TRIM`, plus the totals.

```bash
python .claude/tools/claudemd_audit.py
# CLAUDE.md: 412 lines ~3,100 tokens (budget 1,200) — OVER by 1,900
# [CUT→doc]  ## Architecture        ~820 tok  92% match documentation.md
# [CUT→doc]  ## Chunking strategies  ~240 tok  88% match embeddings.py
# [FIX-REF]  install.py:566          line 566 out of range (file has 540)
# [KEEP]     ## Output style         ~90 tok
# [KEEP]     ## Search before Read    ~70 tok
```

The duplication and ref checks are facts from disk and the index — no model judgment. That is the point.

## Skill, not a prompt line

`skills/claudemd/SKILL.md` carries the rubric + the tool + the procedure as one invocable package. A CLAUDE.md sentence ("keep this file short") is a suggestion that loses to entropy. The skill is a repeatable procedure:

1. Run `claudemd_audit.py`.
2. For each `CUT→doc`: append the section to `documentation.md` (indexed), leave a one-line pointer in CLAUDE.md only if it's a standing rule.
3. For each `FIX-REF`: repair or drop the ref. Prefer symbol names over line numbers — line numbers rot, names don't.
4. For each `TRIM`: rewrite caveman.
5. Re-run audit; confirm under budget.
6. **Verify recall** — for each moved section, run `search.py "<topic>"` and confirm it comes back. If search can't find it, it wasn't safe to cut; restore it.

Step 6 is the safety net: "cut" only holds if the content is still reachable by the mechanism that justified cutting it.

## Hook: enforcement

CLAUDE.md will re-bloat unless something guards it.

**PostToolUse on `Edit`/`Write`**, gated to `file_path` ending in `CLAUDE.md`:

- Recount tokens. Over `CLAUDE_MD_TOKEN_BUDGET` → exit 2: `"CLAUDE.md now ~N tokens (budget M). Run claudemd skill — move detail to documentation.md."`
- Scan added lines for new `path:line` refs and verify them; flag dead refs on the way in, before they rot.

Cheap check, runs on every CLAUDE.md write, keeps the file lean without anyone remembering to.

## Config

Add to `search_config.py`:

```python
# --- CLAUDE.md budget ---
CLAUDE_MD_TOKEN_BUDGET: int = 1200   # always-loaded tax ceiling; 0 disables the hook
CLAUDE_MD_OVERFLOW_DOC: str = "documentation.md"  # where CUT sections land (indexed)
```

## Build order

1. `tools/claudemd_audit.py` — token count + stale-ref check (ship first; immediately useful).
2. Add the duplication/index check (reuses `embeddings.py`).
3. `skills/claudemd/SKILL.md` — rubric + procedure.
4. PostToolUse hook + config + `install.py` wiring.
5. Unit-test the hook via `conftest.load_hook()`; test the audit on a fixture CLAUDE.md.

Per repo lifecycle: CHANGELOG entry on merge, delete the backlog item. Add to BACKLOG under a new "CLAUDE.md hygiene" group when adopted.

## Dogfood

Run it on this repo's own CLAUDE.md first. The Architecture and Chunking-strategy sections are prime `CUT→doc` candidates (they duplicate `documentation.md` and source), and the `install.py:NNN` refs are prime `FIX-REF`. Cutting them is a real, measurable token saving on every turn — proof the skill earns its place.
