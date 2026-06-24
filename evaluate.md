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

The hook scanned tool output, not assistant prose — filler went uncaught. S11 fixes this by moving enforcement to the Stop hook which reads the actual assistant message.

---

## S8 — Symbol index + `/def` lookup

Grep-to-locate dumps hundreds of lines to find one symbol — locating is a deterministic DB lookup, not a reasoning task. `tools/symbols.py` returns exact `file:line:end`; PreToolUse blocks grep on known symbols and routes to `/def`.

---

## S9 — Auto-slice Read (hook computes the slice)

Search already knows the matched line range; Claude reads the whole file anyway. PreToolUse hook reads `last-search` state and rewrites the Read to the exact offset+limit — zero model reasoning, ~90% off large-file reads.

---

## S10 — Post-Edit diff, block the re-Read

Edit already errors on failure, so the verify re-Read is a full-file cost for confirmation already in hand. PostToolUse emits a compact diff; PreToolUse blocks re-Read of any file edited within N seconds.

---

## S11 — Caveman enforcement via Stop hook (fixes the misaim)

Caveman mode had no enforcement — the reminder hook scanned tool output, not Claude's prose. Stop hook reads the last assistant message and checks filler regex + word count; exits 2 on violation.

---

## S12 — Structured tool-output parsers (skill, not prompt)

Blind truncation passes noise and may cut the failing assertion; Claude then reasons over it to find the signal. Parser scripts (pytest → failures+counts, ruff/eslint → `file:line: code`, git → name-status) pipe automatically via PostToolUse on Bash — 60–95% output reduction, signal preserved.

---

## S13 — Adopt Grep-first (backlog S7)

**Verdict: ship it, fold into S8.** PreToolUse blocks reads over threshold and routes to symbol table or search; exempt files already auto-sliced by S9. S7 + S8 + S9 form one pipeline: locate → slice → read.

---

## S6 — Tiered effort (backlog): keep, but honest

**Verdict: low-confidence, weak enforcement.** No hook can force per-turn model downshift; the 50–70% saving claim is unverified. Keep as an opt-in rule; prefer S11 for output-token savings.

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
