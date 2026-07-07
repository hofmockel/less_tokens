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

### Low Priority

- **F3 — Terse hook block messages** *(output)* — block/reminder messages are output tokens, but paid only **on trigger**, not every turn; already trimmed once. Short learned codes (`S9: slice 51-3`) save bytes but need a legend (new fixed cost) and hurt readability. *Verdict: marginal — only worth it for a hook that fires constantly; otherwise skip.*

> **Dual-scope contract (G-series subagents).** Hook-enforced levers land in `agents/common/`, wire into **both** `.claude/settings.json` (matchers `Read|Grep|Glob|Edit|Write|Bash`) and `.codex/hooks.json` (broad `mcp__filesystem__.*` + `apply_patch`, `LESS_TOKENS_AGENT=codex`, `.less_tokens/tools/` shims), and get a row in `agents/common/hooks/parity.json`. Prompt/skill levers land in **both** the Claude skill + `CLAUDE.md` and the Codex `less-tokens` skill + `AGENTS.md`. Respect the wall: `agent_overrides.claude` in `budget.json` is Claude-only by construction. **Codex answer:** Codex exposes `multi_agent_v1.spawn_agent`, `wait_agent`, `send_input`, and `close_agent`, but the tool contract says not to spawn unless the user explicitly asks for subagents, delegation, or parallel agent work. Therefore less_tokens must not sell Codex subagents as autonomous token control; implement them as opt-in skill guidance/templates. The spawn tool is product surface, not an installed project artifact, so CI can test prompt templates and installed hook cwd resolution, but cannot prove real Codex child inheritance end-to-end. **Claude-side ground truth (`.claude/settings.json`):** a Claude child's tool calls *do* fire `PreToolUse`/`PostToolUse`, so search-first, auto-slice, grep-first, read-guard, context-cache, truncate-output compound inside it automatically. But caveman + savings-html are wired only under **`Stop`**, and a subagent emits **`SubagentStop`** (unwired) — so output/terse + savings levers do **not** reach a Claude child until `SubagentStop` is added. `CLAUDE.md` loads once per session: the per-child fixed lever is an agent-definition file (`.claude/agents/<name>.md`) system prompt + `tools:` allowlist, not a slimmer `CLAUDE.md` (none exist yet). Claude Agent-tool children start cold — the native equivalent of Codex `fork_context=false`.

- **G14 — Quarantine dead-end exploration** *(meta)* — route messy "find where X is wired" searches into a subagent so only the conclusion returns; the Reads/greps and dead ends stay in the child window. *Verdict: discipline-only, overlaps G11; worth a skill if exploration is frequent.* **Dual scope:** in-child search-first/grep-first ship for both. Codex viable through `agent_type="explorer"` for specific codebase questions; not viable as an automatic hook because tool usage cannot be intercepted and re-routed into a subagent by this repo.
- **G15 — Propagate hooks into subagents** *(meta)* — ensure a spawned agent's cwd sees `.claude/settings.json` + the venv so search-first/truncate-output/context-cache compound inside the child (caveman is `Stop`-only — see Claude correction). Subagent-specific gotcha: config visibility from the child's working dir. *Verdict: verify + document install behavior; candidate `install.py` test.* **Dual scope:** THE core item, but split acceptance by what the project can own. Claude child inheritance can be tested/documented against `.claude/settings.json`. Codex can only guarantee installed artifacts: `.codex/hooks.json` when writable, `.codex/hooks/`, `.less_tokens/bin/python`, `.less_tokens/tools/`, `AGENTS.md`, and `LESS_TOKENS_AGENT=codex` in hook wrappers. Acceptance: add an install/check test that runs Codex hook wrappers from a nested cwd and proves they resolve repo + venv; document that real spawned Codex agent inheritance is product behavior and must be smoke-tested manually until Codex exposes a test harness. **Claude correction:** the item body overstates it — `caveman` does *not* compound in a Claude child (it's `Stop`; the child emits `SubagentStop`); only `PreToolUse`/`PostToolUse` levers do. Claude acceptance adds `SubagentStop` wiring plus a test that a child tool call fires the project hooks.
- **G16 — Slim the per-agent fixed bucket** *(fixed)* — each child re-pays system/developer prompt + AGENTS/CLAUDE instructions + tool schemas, multiplied by agent count; ship subagents trimmed instructions where the agent product allows it. *Verdict: real fixed-bucket win at fan-out; implementation depends on spawn-config levers.* **Dual scope:** Claude *cannot* slim `CLAUDE.md` per child — it loads once per session; the Claude lever is an agent-definition file (`.claude/agents/<name>.md`) with its own system prompt + a narrow `tools:` allowlist (fewer schemas = smaller fixed tax), none of which exist in this repo yet. Codex currently has no repo-level way to provide a child-specific `AGENTS.md` or disable tool schemas for spawned agents; the viable Codex work is to keep the normal installed `AGENTS.md` tiny (CX5), move detail to the `less-tokens` skill, avoid `fork_context=true` by default, and add a break-even warning to the skill.
- **G17 — Spawn/no-spawn decision rule** *(meta)* — a child costs a full fixed startup tax (system/developer prompt + instruction files + schemas); only spawn when the tokens the child discards exceed that tax. *Verdict: heuristic for a doc/skill, not hook-enforceable.* **Dual scope:** heuristic for both agents' skills, but the break-even constant differs. Codex rule of thumb: do not spawn for a single `rg`, one small file read, or a short test command; consider spawning only for independent exploration, noisy verification, or large-source summarization where the discarded transcript/logs would materially exceed a fresh child startup and the user asked for delegation/parallelism. **Claude side:** Claude's break-even is lower — children start cold (no transcript copy) and parallelize natively, so the startup tax is just system prompt + `CLAUDE.md` + schemas; still skip spawning for a single read/grep/short test.

### Decided against

Rejected proposals moved to [DECISIONS.md](DECISIONS.md) → *Rejected* — record a verdict there before re-proposing.

---

## Vector Search & Indexing

### High Priority

---

## Installer

### High Priority

---

## Hooks & Caveman Mode

(context-cache mtime-staleness bug moved to the **Bugs** table above, 2026-07-04 — confirmed defect, not periphery.)

---

## Prose to Code

Rules, protocols, and configs expressed as natural language that could be deterministic scripts, structured data, or shorter pointers. Ordered by per-turn impact.

### High Priority

### Medium Priority

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
