# Backlog

Planned work not yet started. Maintainer: add `CHANGELOG.md` entry + delete item here before merging. See [.claude/skills/bug-hunt/SKILL.md](.claude/skills/bug-hunt/SKILL.md) / [.claude/skills/bug-hunt/bughuntlog.md](.claude/skills/bug-hunt/bughuntlog.md) for the bug-hunt protocol.

Token-reduction strategies and their rationale live in [evaluate.md](evaluate.md). Items below are tagged with their source `(evaluate.md)`.

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

### Low Priority

- **G7 — Subagent context re-derivation** *(input)* — parent writes a compact context pack (relevant slices + search hits) to `STATE_DIR`; spawned agents read that instead of re-reading/re-searching the same files cold. Mostly a discipline + helper (a skill documenting "pass results, don't re-discover"); hard to hook-enforce. Spiky impact — large only when subagents are used heavily.

- **G10 — Search-result dedup** *(input)* — in `search.py`, drop a hit whose cosine to an already-selected hit exceeds a threshold and backfill the next distinct one, so overlapping/near-duplicate chunks aren't paid for twice per query. Pure post-processing on vectors already in hand; sharpens an existing strategy.
- **S6 — Tiered effort** *(output)* — route tasks to Haiku/Sonnet/Opus by need via `.claude/rules/tier-matrix.md` + an `AGENT_TIER_HINTS: bool` flag. **Verdict (evaluate.md): low confidence.** No hook can force a per-turn model downshift, so enforcement is weak and the claimed 50–70% blended saving is unverified. Keep as an opt-in rule only; prefer the shipped caveman Stop hook for output-token savings. (evaluate.md)

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

- **P1 — `caveman.md` prose → phrase list** *(fixed input)* — `.claude/rules/caveman.md` (always-loaded) describes forbidden phrases conversationally. `VERBOSE_PATTERNS` in `response_budget.py` already IS the machine-readable version. Collapse the rule file to: one-line summary + the patterns list + pointer to the hook. ~50% token reduction every turn.

- **P2 — Hook block messages → trim trailing prose** *(tool output)* — `agents/common/hooks/search_first.py` line 122–123 appends explanatory sentences after the action command. `search-first.py` line 107 adds a third. Both fire on every gate block. Strip to: filename + command only. Same pattern in `grep-first-read.py`. Saves tokens on every blocked call.

### Medium Priority

- **P3 — Bug-hunt stop rule → `tools/hunt_score.py`** *(meta)* — `agents/common/bug-hunt-protocol.md` lines 30–34 describe three numeric thresholds (median severity ≤ `ux`, overlap ≥ 60%, file coverage ≥ 80%) as prose for a human to eyeball. Should be a script: reads structured hunt data, prints `GO` or `STOP` + which signals failed. Requires P4.

- **P4 — `bughuntlog.md` → structured JSONL** *(meta)* — currently free markdown prose per round. Convert to one JSON record per round (bugs found, tiers assigned, overlap count, files hit). Unlocks P3 and makes stop-rule scoring auditable without re-parsing prose.

### Low Priority

- **P5 — `evaluate.md` per-strategy prose → 2-sentence summaries** *(indexed input)* — each S8–S13 section is 100–200 words; the verdict table already captures the essentials. Compress each body to: problem sentence + code-over-reasoning sentence. ~60% word reduction; search hits return tighter chunks.

- **P6 — `search_config.py` comment blocks → inline one-liners** *(read cost)* — multi-paragraph comment blocks precede each config group (e.g. 4-line block before `READ_DENY_GLOBS`). Not in always-loaded context, but inflates read cost when Claude needs the file. Trim each block to one line matching the variable name.

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
