# Backlog

Planned work not yet started. Maintainer: add `CHANGELOG.md` entry + delete item here before merging. See [.claude/skills/bug-hunt/SKILL.md](.claude/skills/bug-hunt/SKILL.md) / [.claude/skills/bug-hunt/bughuntlog.md](.claude/skills/bug-hunt/bughuntlog.md) for the bug-hunt protocol.

Token-reduction strategy and rationale live in [DOCUMENTATION.md](DOCUMENTATION.md) → *Token-reduction strategy*. Shipped strategies use stable IDs (S8–S13). Rejected or resolved proposals move to [DECISIONS.md](DECISIONS.md) — don't re-propose without new evidence.

---

## Bugs

Confirmed defects found by code inspection. Each has a specific file and line reference.

| **Bug** | **Details** | **Status** |
|---|---|---|

---

## Token-Reduction Strategies

Primary mission: fewer tokens. Ordered by impact × enforceability. Each item names the bucket it attacks: **input** (context read in), **output** (prose/code Claude writes), **tool** (tool-result dumps), **fixed** (paid every turn regardless of task), **meta** (multiplies the others). The **fixed** bucket is the biggest blind spot — barely touched beyond the just-shipped claudemd skill.

### High Priority

- **Widen cache keys for bash/grep (normalize + split TTL)** *(input / cache)* — `cacheable_bash_command()`/`grep_key()` key on the exact literal command/pattern string, so semantically-identical repeats (e.g. the same `pytest` call ± `-v`) never hit. Near-miss instrumentation (additive-only) already shipped `f95a963`; zero cached-bash/grep events had fired on the Codex side of this repo specifically because its local `.codex/` install had drifted stale (fixed 2026-07-08 by re-running the installer), not because the allowlist was too narrow — so real Codex near-miss data should now start accumulating. Once a real data window exists: normalize keys by stripping a documented allowlist of output-shape-neutral flags (from the observed near-misses, not a guess) before keying bash commands, hash `(pattern, path, glob, type)` post-normalization for grep, and expose `CONTEXT_CACHE_BASH_TTL` as its own config value (currently silently falls back to the grep TTL). Do not widen the allowlist blind. `eb_telemetry_9jul26.md` §2 has 13 real Claude-side grep near-miss examples from `ever_better` (incl. two same-pattern-reformatted pairs) — useful raw material for the normalization allowlist, but Claude-side, not the Codex-side data this item is actually waiting on.

### Low Priority

*(G14-G17 shipped 2026-07-07 — see CHANGELOG.md. G15's Codex-side nested-cwd bug was fixed after its Bugs-table follow-up.)*

### Decided against

Rejected proposals moved to [DECISIONS.md](DECISIONS.md) → *Rejected* — record a verdict there before re-proposing.

---

## Vector Search & Indexing

### High Priority

---

## Installer

### High Priority

---

## Architecture Simplification

Claude/Codex platform split review. Prefer shared core plus thin adapters; keep divergent paths only where hook surfaces genuinely differ (`Read|Grep|Stop` vs `mcp__filesystem__.*|apply_patch|PostToolUse`).

### Medium Priority

- **Subagent guidance: split shared contract from platform-specific mechanics** *(redundant prose / divergent paths)* — Both skills carry the same output contract, prompt shape, noisy-verification pattern, and large-source digest guidance (`agents/claude/skills/less-tokens/SKILL.md:61-115`, `agents/codex/skills/less-tokens/SKILL.md:54-109`), while the real divergence is Claude agent definitions/tool allowlists versus Codex `fork_context`/`explorer`/`worker` behavior. Factor the shared contract into a common snippet and render only the platform mechanics separately. Acceptance: edits to return shape or "do not paste full files/logs/diffs" happen in one source; platform files retain explicit divergent rules.

- **Parity docs: stop hand-maintaining long platform matrix blocks in multiple docs** *(redundant prose / doc drift)* — The Claude/Codex hook parity matrix is repeated in `README.md:43-68` and `DOCUMENTATION.md:82-107`, while both say the source of truth is `agents/common/hooks/hook_manifest.py` / `parity.json` (`README.md:101`, `DOCUMENTATION.md:109`). Generate these bounded sections from the manifest as part of the existing parity audit/doc update flow. Acceptance: README and documentation matrices are produced from one command and CI fails when generated blocks differ from the manifest.

---

## Hooks & Caveman Mode

(context-cache mtime-staleness bug moved to the **Bugs** table above, 2026-07-04 — confirmed defect, not periphery.)

---

## Prose to Code

Rules, protocols, and configs expressed as natural language that could be deterministic scripts, structured data, or shorter pointers. Ordered by per-turn impact.

### High Priority

### Medium Priority

- **Generate installer flag docs from argparse metadata** *(prose-to-code / doc drift)* — `DOCUMENTATION.md:37-51` hand-lists optional installer flags, but `install.py:1930-1996` is the actual argparse source and already contains richer/current help for flags such as `--create-venv`, `--no-build`, `--dry-run`, `--update`, `--check`, `--uninstall`, and `--codex-savings`. Add a doc renderer/check for an `<!-- installer-flags -->` block sourced from parser metadata or a shared flag registry. Acceptance: docs include every public flag unless explicitly hidden; CI catches stale flag tables.

- **Replace always-loaded test command prose with a dev command shim** *(fixed / prose-to-code)* — `CLAUDE.md:20-31` stores install/test commands and CI matrix prose in always-loaded context, while `pyproject.toml:1-3` and workflows already encode pytest paths. Add a small `.claude/tools/dev.py` or `tools/check.py` command (`unit`, `integration`, `all`, `single <nodeid>`) that uses the configured venv and pytest paths. Then shrink CLAUDE.md to "run dev.py test" plus a pointer to docs for the matrix. Acceptance: local unit/integration commands and CI paths share one source; CLAUDE.md loses the multi-line command block.

- **Code the root-doc canonical-home rules** *(meta / prose-to-code)* — The claudemd skill carries a hand-maintained canonical-home table for root docs (`.claude/skills/claudemd/SKILL.md:71-84`) and asks the agent to check/collapse duplicates manually. Move those topic homes into structured config consumed by `claudemd_audit.py --docs` or a new `docs_canonical_gate.py` that scans README/DOCUMENTATION/CLAUDE/AGENTS/rules for duplicate topic headings or configured keywords. Acceptance: the skill keeps only a pointer to the gate; CI or release check reports non-canonical duplicate sections with file:line refs.

---

## README Accuracy

### Inaccurate

### Language / Precision

---

## Claude Agent

Claude-only token savings. Isolation walls: `agent_overrides.claude` in `.less_tokens/config/budget.json` (deep-merged per-agent at `agents/common/budget/config.py:82-84`, so Codex never sees it) and `.claude/settings.json` hook wiring (separate file from `.codex/hooks.json`). Touch only those and Codex is unaffected by construction.

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

- **Bugfix skill: add same-pattern propagation step** *(process)* — After fixing any bug, require a codebase-wide search for the same pattern before closing. Add explicit checklist step to `.claude/skills/bugfix/SKILL.md`: grep for the root-cause construct (e.g. `endswith`, `offset`) across all `.py` files; open a backlog row for each additional hit. Prevents `endswith` and `offset=0` class of duplicates.

- **Consider GitHub self-hosted runners for the perf job** — the `perf` CI job downloads the fastembed model (~130 MB `BAAI/bge-small-en-v1.5`) and relies on `actions/cache`; a cold cache miss adds wall-clock time and network variance to timing results. A self-hosted runner with the model pre-installed in `~/.cache/huggingface` would remove both and give stable CPU baselines. Trade-off: infra maintenance + runner registration; only worth it if perf run times become a bottleneck or variance produces false failures. (Demoted: not on the token-reduction mission.)

---
