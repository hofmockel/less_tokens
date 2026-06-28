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

> **Dual-scope contract (G-series subagents).** Hook-enforced levers land in `agents/common/`, wire into **both** `.claude/settings.json` (matchers `Read|Grep|Glob|Edit|Write|Bash`) and `.codex/hooks.json` (broad `mcp__filesystem__.*` + `apply_patch`, `LESS_TOKENS_AGENT=codex`, `.less_tokens/tools/` shims), and get a row in `agents/common/hooks/parity.json`. Prompt/skill levers land in **both** the Claude skill + `CLAUDE.md` and the Codex `less-tokens` skill + `AGENTS.md`. Respect the wall: `agent_overrides.claude` in `budget.json` is Claude-only by construction. **Open question each spawn-mechanic item must resolve: does Codex expose a subagent/spawn primitive?** If not, the spawn step is Claude-only, but the in-child enforcement still belongs in `common/` so it covers Codex's primary context and any future Codex sub-process.

- **G8 — Parallel subagent dispatch** *(meta)* — spawn independent subtasks concurrently so each keeps a small context instead of one bloated parent thread; same wall-clock. No helper/skill today. *Verdict: discipline-only, not hook-enforceable; worth a thin skill if subagent use grows.* **Dual scope:** spawn primitive is Claude's Agent tool; Codex equivalent unconfirmed (flag). Heuristic lives in both agents' skills; startup-tax math differs (Claude system prompt + `CLAUDE.md` + tool schemas vs Codex `AGENTS.md` + filesystem-MCP schemas).
- **G9 — Output contracts for subagents** *(input)* — parent prompt template pins exactly what the agent returns ("file:line list, no code") so the final message stays small. Ship as a prompt snippet/skill; no enforcement hook possible. *Verdict: low cost, marginal until subagents run often.* **Dual scope:** in-child enforcement is free — caveman/terse-output already ships for both (parity.json); only the return-shape instruction is per-agent, so encode it in both the Claude subagent prompt and the Codex `less-tokens` skill.
- **G11 — Isolate noisy verification in a subagent** *(tool)* — run test/lint/build loops inside a spawned agent; failures, retries, stack traces stay in its window, parent gets pass/fail + summary. Complements `lean-output` (which trims in-context) by moving the whole loop out of the parent. *Verdict: real tool-bucket win when verification is noisy; needs a skill, no hook.* **Dual scope:** the in-child trim reuses `lean-output` (shipped both, parity.json); only the spawn-to-isolate step is Claude-specific until the Codex spawn primitive is confirmed.
- **G12 — Summarize-then-discard large reads via subagent** *(input)* — agent ingests a big doc/log and returns a digest; the source never enters the parent. Complements auto-slice/truncation (in-context) by pushing the full read across the agent boundary. *Verdict: useful for one-off large sources; discipline/skill, not hook-enforceable.* **Dual scope:** write the digest to `.less_tokens/state/` (shared path) in an agent-neutral format, so a Codex child and a Claude parent (or vice versa) interoperate — cross-agent handoff becomes a feature, not a port.
- **G13 — Pointer-not-payload spawn prompts** *(input)* — pass `path:line` + a search query in the spawn prompt instead of pasted files; the child's search-first fetches only what it needs. Avoids double-billing the same bytes as parent output then child input. *Verdict: prompt discipline/skill; pairs with G7.* **Dual scope:** prompt discipline in both agents' skills; pointers resolve via search-first, which already ships for both (parity.json), so no new hook — just the per-agent prompt template.
- **G14 — Quarantine dead-end exploration** *(meta)* — route messy "find where X is wired" searches into a subagent so only the conclusion returns; the Reads/greps and dead ends stay in the child window. *Verdict: discipline-only, overlaps G11; worth a skill if exploration is frequent.* **Dual scope:** same split as G11 — in-child search-first/grep-first ship for both; the spawn mechanic is per-agent and gated on the Codex-subagent question.
- **G15 — Propagate hooks into subagents** *(meta)* — ensure a spawned agent's cwd sees `.claude/settings.json` + the venv so search-first/truncate-output/context-cache/caveman compound inside the child. Subagent-specific gotcha: config visibility from the child's working dir. *Verdict: verify + document install behavior; candidate `install.py` test.* **Dual scope:** THE core item. Claude child inherits `.claude/settings.json`; a Codex child needs `.codex/hooks.json` + `.less_tokens/bin/python` + `LESS_TOKENS_AGENT=codex` reachable from its cwd. Acceptance: an `install.py` test per agent that proves a spawned process's cwd resolves the hooks + venv, plus a `parity.json` row.
- **G16 — Slim the per-agent fixed bucket** *(fixed)* — each child re-pays system prompt + CLAUDE.md + tool schemas, multiplied by agent count; ship subagents a trimmed CLAUDE.md / fewer always-on skills. *Verdict: real fixed-bucket win at fan-out; needs a spawn-config lever, reuses the claudemd approach.* **Dual scope:** Claude trims the subagent `CLAUDE.md`; Codex trims `AGENTS.md` (builds on shipped CX5 + `CODEX_AGGRESSIVE_AGENTS_NOTE`). Do both separately — the fixed bucket and its file differ per agent.
- **G17 — Spawn/no-spawn decision rule** *(meta)* — a child costs a full fixed startup tax (system prompt + CLAUDE.md + schemas); only spawn when the tokens the child discards exceed that tax. *Verdict: heuristic for a doc/skill, not hook-enforceable.* **Dual scope:** heuristic for both agents' skills, but the break-even constant differs — Claude's startup tax is system prompt + `CLAUDE.md` + tool schemas; Codex's is `AGENTS.md` + filesystem-MCP schemas. State both thresholds.

### Decided against (record to prevent re-proposal)

- **F4 — Consolidate overlapping tools** *(meta)* — `search.py`/`search_config.py`/`symbols.py`/`parse.py` have distinct jobs (search runtime / config / symbol index / AST parse). Merging is pure refactor: zero token saving, real regression risk across both agents. Not worth it.
- **G10 — Bound subagent search breadth** *(input)* — the harness Explore agent already exposes a breadth knob (medium / very thorough); less_tokens adds nothing and cannot hook-enforce a sub-process's search scope. Owned by the harness, not this toolkit. Skip. **Dual scope:** Explore's breadth knob is a Claude harness feature; Codex has no equivalent. Skip for both — distinct reasons, recorded so neither agent re-proposes it.
- **S6 — Tiered effort** *(output)* — route tasks to Haiku/Sonnet/Opus via a tier matrix + flag. No hook can force a per-turn model downshift, so enforcement is weak and the claimed 50–70% saving is unverified. The shipped caveman Stop hook already captures output-token savings deterministically. Skip.

---

## Vector Search & Indexing

### High Priority

---

## Installer

### High Priority

---

## Hooks & Caveman Mode

- **Terse-output mode should exempt human-readable document drafting** *(output / docs quality)* — The terse-output rule is useful for chat replies, status updates, and routine engineering handoffs, but it is the wrong default when the agent is asked to write or revise artifacts meant for humans to read: `README.md`, `DOCUMENTATION.md`, release notes, proposals, reports, Word/PDF/slide content, long-form explanations, and other polished documents. The hook/rule should distinguish "assistant response should be concise" from "the requested artifact should be readable." Fix options: (a) add explicit guidance to `.claude/rules/caveman.md` and `CLAUDE.md` that human-facing artifacts are exempt from terse style; (b) teach `caveman-reminder.py` to skip enforcement when the last assistant turn mostly contains document content or when the user asks for docs/prose; (c) add a narrow bypass marker for document-writing turns. Acceptance: document edits should optimize for clarity, flow, and audience rather than clipped phrasing, while ordinary assistant commentary stays concise.

- **context-cache trusts mtime as proof of "unchanged"** *(tool / correctness)* — `check_read` ([agents/common/hooks/context_cache.py:88-97](agents/common/hooks/context_cache.py)) blocks a re-Read when `Path(file_path).stat().st_mtime` equals the recorded mtime, and the block message asserts "file unchanged. Skip this Read; content is still valid in context." mtime equality is **not** content equality: coarse filesystem mtime granularity, mtime-preserving writes (`cp -p`, `git checkout`/revert, `rsync --times`, editors that restore mtime), or clock skew can change the bytes while leaving mtime untouched. The hook then tells the agent stale content is current — and any `Edit` built on that cached view matches against the wrong text, silently. Likelihood is low and the upside (token saving) is real, but the failure mode lands on **edit correctness**, not just tokens, and is invisible when it happens. *Fix options, cheapest first: (a) add `st_size` to the cache entry + comparison (one extra field, catches most same-mtime content changes); (b) soften the message from "file unchanged" to "likely unchanged — re-read if you need exact bytes"; (c) key on a content hash for full correctness (most expensive, defeats some of the saving). Observed 2026-06-26 — fell back to `cat` to get exact strings for an Edit because the Read was cache-blocked.*

---

## Prose to Code

Rules, protocols, and configs expressed as natural language that could be deterministic scripts, structured data, or shorter pointers. Ordered by per-turn impact.

### High Priority

### Medium Priority

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

- **Consider GitHub self-hosted runners for the perf job** — the `perf` CI job downloads the fastembed model (~130 MB `BAAI/bge-small-en-v1.5`) and relies on `actions/cache`; a cold cache miss adds wall-clock time and network variance to timing results. A self-hosted runner with the model pre-installed in `~/.cache/huggingface` would remove both and give stable CPU baselines. Trade-off: infra maintenance + runner registration; only worth it if perf run times become a bottleneck or variance produces false failures. (Demoted: not on the token-reduction mission.)

---
