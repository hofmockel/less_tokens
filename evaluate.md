# evaluate.md — Code-over-Reasoning Strategies

Status update, 21 Jun 2026: the core S8-S13 implementation described below has landed for Claude, and Codex now has parity-oriented adapters for the high-value read/output guards. `symbols.py` covers Python plus JS/TS definitions; Codex installs wire read guard, auto-slice, grep-first read, read-after-edit, context cache, listing guard, lean-output, post-edit diff, index refresh, and AGENTS.md budget checks when `.codex/hooks.json` is writable. Remaining work is tracked in `BACKLOG.md`.

Goal: cut tokens. Prefer deterministic code over Claude reasoning. Prefer skills over prompt text. Hooks enforce — a rule nobody enforces gets ignored.

Read BACKLOG.md first. Backlog already holds S6 (Tiered Effort) and S7 (Grep-before-Read). This doc adds S8–S13 plus verdicts on the two backlog proposals. Minimal-impact ideas cut on purpose (see bottom).

---

## Lens

Every token Claude spends falls in three buckets:

- **Input** — files read, search results, history. Biggest lever (5–10×).
- **Output** — Claude prose. Caveman attacks this.
- **Tool** — raw dumps from Bash/Read/WebFetch. Truncation attacks this.

"Code over reasoning" means: when a deterministic script can produce the answer, do not make the model read + think to get there. "Hook enforces" means: PreToolUse blocks the wasteful action; PostToolUse rewrites or trims the result. A CLAUDE.md sentence is a suggestion. A hook is law.

---

## Verdict table

| # | Strategy | Lever | Type | Enforced by | Effort | Est. saving |
|---|---|---|---|---|---|---|
| S8 | Symbol index + `/def` | Input | Code (tool+cmd) | PreToolUse Read/Grep | ~3h | locate cost ~0, kills grep dumps |
| S9 | Auto-slice Read | Input | Code (hook computes offset) | PreToolUse Read | ~2h | 70–90% per large-file Read |
| S10 | Post-Edit diff, block re-Read | Input | Hook | Pre+PostToolUse Edit | ~2h | full re-Read per edit |
| S11 | Caveman Stop-hook (fix misaim) | Output | Hook | Stop | ~2h | makes caveman real |
| S12 | Structured tool parsers | Tool | Skill | PostToolUse wrap | ~3h | 60–95% on test/lint/git |
| S13 | Grep-first (adopt S7) | Input | Hook | PreToolUse Read | ~1h | 150+ lines per blocked Read |
| S6 | Tiered effort (backlog) | Output | Rule | weak | ~1h | claims 50–70%, unenforceable |

---

## Critical finding: caveman enforcement is misaimed

`.claude/hooks/caveman-reminder.py` scans `tool_result` for filler phrases. But filler lives in **Claude's prose**, not in tool output. Bash/Read results almost never say "I'd be happy to." So the one hook guarding the output-token strategy rarely fires on the real offender. Caveman mode today is a CLAUDE.md suggestion with no teeth. S11 fixes this.

---

## S8 — Symbol index + `/def` lookup

**Problem.** Claude locates a function by reasoning: grep the name, read the dump, pick the line, then Read the file. Grep alone can dump hundreds of lines. Pure waste — locating a symbol is deterministic.

**Code over reasoning.** Build a symbol→`file:line:end` map at index time. `embeddings.py` already AST-parses Python (`chunk_python`) and splits SQL/markdown. Same pass emits a symbol table into `index.db`. Lookup is an O(1) DB hit, not a model decision.

**Pieces.**

1. `tools/symbols.py` — `symbols.py <name>` → `path:start-end` rows, exact ranges. Reuse the AST walk already in `embeddings.py`. New table:

```sql
CREATE TABLE symbols (
  name TEXT, kind TEXT, source_path TEXT,
  start_line INTEGER, end_line INTEGER,
  PRIMARY KEY (name, source_path, start_line)
);
```

2. `commands/def.md` — `/def <symbol>` slash command wrapping the tool.

3. **Enforcement** — extend `hooks/search-first.py`: a `Grep`/`Bash grep` for a bare identifier that exists in `symbols` gets blocked with `"foo is a known symbol. /def foo for exact location."` Symbol lookup returns 1 line; grep returns the dump.

**Why code.** The location is a fact in the DB. No reasoning, no dump, no read-to-find.

---

## S9 — Auto-slice Read (hook computes the slice)

**Problem.** Search returns the right chunk, then Claude Reads the **whole file** anyway "for context." The chunk's line range is already known — recomputing which lines to read is reasoning that code can do.

**Code over reasoning.** `search.py` already knows each hit's `start_line`/`end_line` (and S8's symbol table makes it exact). On a `Read` of an indexed file with no `offset`, the PreToolUse hook looks up the last search's matched range for that path and **computes** offset+limit, then blocks with the exact targeted command:

```
foo.py is 600 lines. Last search matched lines 210–248.
Read(foo.py, offset=205, limit=50) — not the whole file.
```

Claude obeys a computed instruction; it does not decide the range. If the host's Claude Code build supports `updatedInput` on PreToolUse, the hook rewrites the call directly — zero model involvement. Otherwise it blocks with the computed slice. Either way the math is in code.

**Enforcement.** PreToolUse on `Read`, gated to indexed files, reading `STATE_DIR/last-search` (already written every search).

**Saving.** A 600-line file read as a 50-line slice ≈ 90% off that Read. This is the headline lever.

---

## S10 — Post-Edit diff, block the re-Read

**Problem.** After `Edit`, Claude re-Reads the file to "verify." Edit already errors on failure, so the re-Read is a full-file input cost for confirmation it already has. Classic reasoning-instead-of-fact.

**Code over reasoning.**

1. **PostToolUse on `Edit`/`Write`** — emit a tight unified diff (`git diff -U2 -- <file>` or difflib on the known before/after). Claude sees exactly what changed, in a handful of lines.

2. **PreToolUse on `Read`** — if `<file>` was edited within N seconds (track in `STATE_DIR/last-edit`), block: `"You just edited foo.py; diff already shown above. Re-Read only if you need unrelated lines."`

**Saving.** Replaces a full-file Read after every edit with a 2–10 line diff. Edit-heavy sessions edit constantly.

---

## S11 — Caveman enforcement via Stop hook (fixes the misaim)

**Problem.** See critical finding. The output-token strategy has no working enforcement.

**Code over reasoning.** A `Stop` hook reads the **last assistant message** from `transcript_path` (compact-trigger already consumes that path, so the plumbing exists) and checks it deterministically:

- filler regex (reuse `VERBOSE_PATTERNS`)
- word count over a budget (config `MAX_RESPONSE_WORDS`, exempt code fences)

On violation, exit 2 with `"Response verbose (N words / filler hit). Caveman mode: cut to facts, retry."` Now the rule that defines the strategy actually fires on the text it governs.

**Config.** Add `MAX_RESPONSE_WORDS` and a `CAVEMAN_ENFORCE: bool` to `search_config.py`. Wire the Stop hook in `install.py` under `--caveman`.

**Note.** Pairs with the open backlog item "Per-task exemptions" — let CLAUDE.md whitelist task types (PR text, user copy) that skip the check.

---

## S12 — Structured tool-output parsers (skill, not prompt)

**Problem.** Truncation (S3) blindly head/tails. A 2000-line pytest run truncated to 4000 chars still wastes tokens AND may cut the failing assertion. Claude then reasons over noise to find the one failure.

**Skill over prompt.** Ship a `skills/lean-output/` skill with thin parsers that return **only what matters**:

- pytest → failing test ids + assertion lines + counts
- ruff/eslint → `file:line: code msg` rows only
- `git status`/`diff` → name-status + stat, not full hunks unless asked

```bash
pytest -q | python .claude/tools/parse.py pytest   # 1200 lines -> ~8
```

A skill (with the parser scripts beside it) beats a CLAUDE.md sentence: it carries the exact commands and runs deterministically. **PostToolUse on `Bash`** can auto-detect known tools (pytest/ruff/git in the command) and pipe through the parser before the result reaches context — enforcement without Claude remembering.

**Saving.** 60–95% on the noisiest, most-repeated tool outputs, and the signal survives.

---

## S13 — Adopt Grep-first (backlog S7)

**Verdict: ship it, fold into S8.** Sound and code-driven. The PreToolUse `Read` block on files over a line threshold is the right shape. Refinements: exempt files S9 already auto-slices (no double-gate), and route the "find the line" step to S8's `/def` / symbol table instead of raw `grep -n` so the locate step is also deterministic. S7 + S8 + S9 form one input-token pipeline: locate by symbol → read only the slice.

---

## S6 — Tiered effort (backlog): keep, but honest

**Verdict: low-confidence, weak enforcement.** Routing tasks to Haiku/Sonnet/Opus genuinely saves output tokens, but a CLAUDE.md "emit a tier line" rule is a suggestion the model drops under load — no hook can force the model to downshift mid-session, and Cowork/Claude Code don't expose per-turn model switching to a hook. Keep as a rule, but do not count on the 50–70% claim. Higher-certainty output savings come from S11 (enforced caveman). Prioritize S11 over S6.

---

## Cut: minimal-impact ideas (deliberately not proposed)

- **Savings dashboard artifact (live HTML).** Pretty observability, zero effect on tokens spent. Out of scope for the mission.
- **search.py REPL / file-watcher** (already low-priority in backlog). DX, not token reduction.
- **Query/result cache.** Saves embedding compute, not context tokens.
- **Search-quality logging.** Audit aid, not a saving.

These touch the periphery. The mission is fewer tokens; S8–S12 hit input/output/tool directly and are enforced by code.

---

## Build order

1. **S11** — fix the broken enforcement first; cheap, makes an existing strategy real.
2. **S9 + S13 + S8** — the input-token pipeline; biggest lever.
3. **S10** — kills a constant edit-loop waste.
4. **S12** — wrap the noisiest tools.

Each lands as: tool/parser in `tools/`, hook in `hooks/`, config in `search_config.py`, wired by `install.py`, unit-tested via `conftest.load_hook()`. Per repo lifecycle: CHANGELOG entry on merge, delete the backlog item.
