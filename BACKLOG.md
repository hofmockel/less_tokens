# Backlog

Planned work not yet started. Maintainer: add `CHANGELOG.md` entry + delete item here before merging. See [.claude/skills/bug-hunt/SKILL.md](.claude/skills/bug-hunt/SKILL.md) / [.claude/skills/bug-hunt/bughuntlog.md](.claude/skills/bug-hunt/bughuntlog.md) for the bug-hunt protocol.

Token-reduction strategy and rationale live in [DOCUMENTATION.md](DOCUMENTATION.md) → *Token-reduction strategy*. Shipped strategies use stable IDs (S8–S13).

---

## Bugs

Confirmed defects found by code inspection. Each has a specific file and line reference.

| **Bug** | **Details** | **Status** |
|---|---|---|

---

## Token-Reduction Strategies

Primary mission: fewer tokens. Ordered by impact × enforceability. Each item names the bucket it attacks: **input** (context read in), **output** (prose/code Claude writes), **tool** (tool-result dumps), **fixed** (paid every turn regardless of task), **meta** (multiplies the others). The **fixed** bucket is the biggest blind spot — barely touched beyond the just-shipped claudemd skill.

### High Priority

### Medium Priority

- **F2 — Doc dedup to one source of truth** *(fixed)* — README, BACKLOG, and DOCUMENTATION.md overlap. Pick one canonical home per topic, replace the duplicates with pointers. Point the `claudemd` skill at the other root docs, not just CLAUDE.md.
- **F3 — Terse hook block messages** *(output)* — block/reminder messages are output tokens paid on every trigger. Already trimmed once; push to short learned codes (e.g. `S9: slice 51-3`) instead of sentences across all hooks in `.claude/hooks/`.

### Low Priority

- **F4 — Consolidate overlapping tools** *(meta)* — 18 files in `.claude/tools/`; `search.py`/`search_config.py`/`symbols.py`/`parse.py` likely fold into fewer entry points. Less surface, less duplication to maintain across both agents. Low priority — refactor, verify before merging.
- **G7 — Subagent context re-derivation** *(input)* — parent writes a compact context pack (relevant slices + search hits) to `STATE_DIR`; spawned agents read that instead of re-reading/re-searching the same files cold. Mostly a discipline + helper (a skill documenting "pass results, don't re-discover"); hard to hook-enforce. Spiky impact — large only when subagents are used heavily.

- **G10 — Search-result dedup** *(input)* — in `search.py`, drop a hit whose cosine to an already-selected hit exceeds a threshold and backfill the next distinct one, so overlapping/near-duplicate chunks aren't paid for twice per query. Pure post-processing on vectors already in hand; sharpens an existing strategy.
- **S6 — Tiered effort** *(output)* — route tasks to Haiku/Sonnet/Opus by need via `.claude/rules/tier-matrix.md` + an `AGENT_TIER_HINTS: bool` flag. **Verdict: low confidence.** No hook can force a per-turn model downshift, so enforcement is weak and the claimed 50–70% blended saving is unverified. Keep as an opt-in rule only; prefer the shipped caveman Stop hook for output-token savings.

---

## Vector Search & Indexing

### High Priority

---

## Installer

### High Priority

---

## Hooks & Caveman Mode

---

## Prose to Code

Rules, protocols, and configs expressed as natural language that could be deterministic scripts, structured data, or shorter pointers. Ordered by per-turn impact.

### High Priority

- **P1 — Delete hook-duplicating prose from CLAUDE.md** *(fixed)* — every CLAUDE.md sentence that merely restates a rule a hook already enforces (e.g. "Search before Read" → `search-first.py`, read-after-edit guidance → `read-after-edit.py`) is paid on every turn and enforces nothing; the hook is law, the prose is suggestion. Audit CLAUDE.md against `.claude/hooks/`, delete prose whose rule is hook-enforced. Cheapest fixed-bucket win, zero behavior risk.

### Medium Priority

- **P3 — Fix `is_indexed()` divergence instead of documenting it** *(fixed)* — CLAUDE.md "Known bugs worth avoiding" warns that `is_indexed()` behaves differently in `search-first.py` vs `index-refresh.py`. The warning costs tokens every turn forever; one shared implementation deletes both the bug and the warning. Prefer the fix to the landmine note.



---

## Codex Agent

### High Priority

- **C1 — Single source, two emitters** *(meta)* — define each hook once in `agents/common/hooks/` and generate both `.claude/settings` and `.codex/hooks.json` wiring from one manifest. The format difference becomes a translator, not a fork. Pays down the two-agent maintenance tax at its root.
- **C2 — Finish shared-hook extraction** *(meta)* — context-cache, listing-guard, and post-edit-diff are Codex-local with no `agents/common/hooks/` counterpart; extract shared logic so Claude adapters reuse without duplication. 
### Medium Priority

- **C3 — CI-checked parity matrix** *(meta)* — data file mapping each hook × {claude, codex} = shipped/missing; CI fails on unintended gaps. Replaces hand-dated per-doc status prose (the kind retired with `evaluate.md`) and surfaces parity debt at a glance.
- **Codex `apply_patch` path extraction** — parse touched file paths from `apply_patch` payloads in `.codex/hooks/index-refresh.py` instead of triggering a full conservative `embeddings.py refresh`; reduces unnecessary index churn on patch-only edits.
### Low Priority

---

## Developer Experience

### Low Priority

- **Consider GitHub self-hosted runners for the perf job** — the `perf` CI job downloads the fastembed model (~130 MB `BAAI/bge-small-en-v1.5`) and relies on `actions/cache`; a cold cache miss adds wall-clock time and network variance to timing results. A self-hosted runner with the model pre-installed in `~/.cache/huggingface` would remove both and give stable CPU baselines. Trade-off: infra maintenance + runner registration; only worth it if perf run times become a bottleneck or variance produces false failures. (Demoted: not on the token-reduction mission.)

---
