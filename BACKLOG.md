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

### Low Priority

- **F3 — Terse hook block messages** *(output)* — block/reminder messages are output tokens, but paid only **on trigger**, not every turn; already trimmed once. Short learned codes (`S9: slice 51-3`) save bytes but need a legend (new fixed cost) and hurt readability. *Verdict: marginal — only worth it for a hook that fires constantly; otherwise skip.*
- **G7 — Subagent context re-derivation** *(input)* — parent writes a compact context pack (relevant slices + search hits) to `STATE_DIR`; spawned agents read that instead of re-reading/re-searching cold. Discipline + helper skill; hard to hook-enforce. *Verdict: defer — spiky, only pays when subagents run heavily.*

### Decided against (record to prevent re-proposal)

- **F4 — Consolidate overlapping tools** *(meta)* — `search.py`/`search_config.py`/`symbols.py`/`parse.py` have distinct jobs (search runtime / config / symbol index / AST parse). Merging is pure refactor: zero token saving, real regression risk across both agents. Not worth it.
- **S6 — Tiered effort** *(output)* — route tasks to Haiku/Sonnet/Opus via a tier matrix + flag. No hook can force a per-turn model downshift, so enforcement is weak and the claimed 50–70% saving is unverified. The shipped caveman Stop hook already captures output-token savings deterministically. Skip.

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

### Medium Priority

---

## Codex Agent

### High Priority

### Medium Priority

### Low Priority

---

## Developer Experience

### Low Priority

- **Consider GitHub self-hosted runners for the perf job** — the `perf` CI job downloads the fastembed model (~130 MB `BAAI/bge-small-en-v1.5`) and relies on `actions/cache`; a cold cache miss adds wall-clock time and network variance to timing results. A self-hosted runner with the model pre-installed in `~/.cache/huggingface` would remove both and give stable CPU baselines. Trade-off: infra maintenance + runner registration; only worth it if perf run times become a bottleneck or variance produces false failures. (Demoted: not on the token-reduction mission.)

---
