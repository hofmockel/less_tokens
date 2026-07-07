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

> **Dual-scope contract (G-series subagents).** Hook-enforced levers land in `agents/common/`, wire into **both** `.claude/settings.json` (matchers `Read|Grep|Glob|Edit|Write|Bash`) and `.codex/hooks.json` (broad `mcp__filesystem__.*` + `apply_patch`, `LESS_TOKENS_AGENT=codex`, `.less_tokens/tools/` shims), and get a row in `agents/common/hooks/parity.json`. Prompt/skill levers land in **both** the Claude skill + `CLAUDE.md` and the Codex `less-tokens` skill + `AGENTS.md`. Respect the wall: `agent_overrides.claude` in `budget.json` is Claude-only by construction. **Codex answer:** Codex exposes `multi_agent_v1.spawn_agent`, `wait_agent`, `send_input`, and `close_agent`, but the tool contract says not to spawn unless the user explicitly asks for subagents, delegation, or parallel agent work. Therefore less_tokens must not sell Codex subagents as autonomous token control; implement them as opt-in skill guidance/templates. The spawn tool is product surface, not an installed project artifact, so CI can test prompt templates and installed hook cwd resolution, but cannot prove real Codex child inheritance end-to-end. **Claude-side ground truth (`.claude/settings.json`):** a Claude child's tool calls *do* fire `PreToolUse`/`PostToolUse`, so search-first, auto-slice, grep-first, read-guard, context-cache, truncate-output compound inside it automatically. But caveman + savings-html are wired only under **`Stop`**, and a subagent emits **`SubagentStop`** (unwired) — so output/terse + savings levers do **not** reach a Claude child until `SubagentStop` is added. `CLAUDE.md` loads once per session: the per-child fixed lever is an agent-definition file (`.claude/agents/<name>.md`) system prompt + `tools:` allowlist, not a slimmer `CLAUDE.md` (none exist yet). Claude Agent-tool children start cold — the native equivalent of Codex `fork_context=false`.

- **G8 — Parallel subagent dispatch** *(meta)* — spawn independent subtasks concurrently so each keeps a small context instead of one bloated parent thread; same wall-clock. No helper/skill today. *Verdict: discipline-only, not hook-enforceable; worth a thin skill if subagent use grows.* **Dual scope:** Claude uses its Agent tool. Codex can use `multi_agent_v1.spawn_agent` only after explicit user authorization; prefer `agent_type="explorer"` for specific read-only code questions and `agent_type="worker"` only with disjoint file ownership. Default `fork_context=false` to avoid copying the parent transcript unless the child truly needs prior conversation. Heuristic lives in both agents' skills; startup-tax math differs (Claude system prompt + `CLAUDE.md` + tool schemas vs Codex system/developer stack + `AGENTS.md` + callable tool schemas). **Claude side:** the Agent tool is present today and its children start cold + parallelize natively (the `fork_context=false` default), so build the dispatch helper now without gating on Codex.
- **G9 — Output contracts for subagents** *(input)* — parent prompt template pins exactly what the agent returns ("file:line list, no code") so the final message stays small. Ship as a prompt snippet/skill; no enforcement hook possible. *Verdict: low cost, marginal until subagents run often.* **Dual scope:** in-child terse-output does *not* even run on a Claude child — caveman is a `Stop` hook and a subagent emits `SubagentStop` (unwired), so wire caveman to `SubagentStop` or the return contract is prompt-only. Codex children should be prompted for `files changed`, `findings`, `verification`, and `blockers` only, with line references and no pasted file bodies/logs. Encode this in both the Claude subagent prompt and the Codex `less-tokens` skill.
- **G11 — Isolate noisy verification in a subagent** *(tool)* — run test/lint/build loops inside a spawned agent; failures, retries, stack traces stay in its window, parent gets pass/fail + summary. Complements `lean-output` (which trims in-context) by moving the whole loop out of the parent. *Verdict: real tool-bucket win when verification is noisy; needs a skill, no hook.* **Dual scope:** the in-child trim reuses `lean-output` (shipped both, parity.json). Codex viability is opt-in only; delegate verification when it can run while the parent continues non-overlapping work, otherwise the child startup tax plus waiting can cost more than a lean local command. **Claude side:** the verification child works today via the Agent tool; `lean-output` trims inside it through `PostToolUse`, which *does* fire in Claude children.
- **G12 — Summarize-then-discard large reads via subagent** *(input)* — agent ingests a big doc/log and returns a digest; the source never enters the parent. Complements auto-slice/truncation (in-context) by pushing the full read across the agent boundary. *Verdict: useful for one-off large sources; discipline/skill, not hook-enforceable.* **Dual scope:** write the digest to `.less_tokens/state/` (shared path) in an agent-neutral format, so a Codex child and a Claude parent (or vice versa) interoperate. For Codex, pass `fork_context=false` and a pointer to the source; require the return to include digest path + source path + enough line refs to verify, not the original payload. **Claude side:** a Claude child returns the digest directly in its Agent-tool return message — no `.less_tokens/state/` file needed; that shared file is the Codex / cross-agent path only, so don't force Claude through the indirection.
- **G14 — Quarantine dead-end exploration** *(meta)* — route messy "find where X is wired" searches into a subagent so only the conclusion returns; the Reads/greps and dead ends stay in the child window. *Verdict: discipline-only, overlaps G11; worth a skill if exploration is frequent.* **Dual scope:** in-child search-first/grep-first ship for both. Codex viable through `agent_type="explorer"` for specific codebase questions; not viable as an automatic hook because tool usage cannot be intercepted and re-routed into a subagent by this repo.
- **G15 — Propagate hooks into subagents** *(meta)* — ensure a spawned agent's cwd sees `.claude/settings.json` + the venv so search-first/truncate-output/context-cache compound inside the child (caveman is `Stop`-only — see Claude correction). Subagent-specific gotcha: config visibility from the child's working dir. *Verdict: verify + document install behavior; candidate `install.py` test.* **Dual scope:** THE core item, but split acceptance by what the project can own. Claude child inheritance can be tested/documented against `.claude/settings.json`. Codex can only guarantee installed artifacts: `.codex/hooks.json` when writable, `.codex/hooks/`, `.less_tokens/bin/python`, `.less_tokens/tools/`, `AGENTS.md`, and `LESS_TOKENS_AGENT=codex` in hook wrappers. Acceptance: add an install/check test that runs Codex hook wrappers from a nested cwd and proves they resolve repo + venv; document that real spawned Codex agent inheritance is product behavior and must be smoke-tested manually until Codex exposes a test harness. **Claude correction:** the item body overstates it — `caveman` does *not* compound in a Claude child (it's `Stop`; the child emits `SubagentStop`); only `PreToolUse`/`PostToolUse` levers do. Claude acceptance adds `SubagentStop` wiring plus a test that a child tool call fires the project hooks.
- **G16 — Slim the per-agent fixed bucket** *(fixed)* — each child re-pays system/developer prompt + AGENTS/CLAUDE instructions + tool schemas, multiplied by agent count; ship subagents trimmed instructions where the agent product allows it. *Verdict: real fixed-bucket win at fan-out; implementation depends on spawn-config levers.* **Dual scope:** Claude *cannot* slim `CLAUDE.md` per child — it loads once per session; the Claude lever is an agent-definition file (`.claude/agents/<name>.md`) with its own system prompt + a narrow `tools:` allowlist (fewer schemas = smaller fixed tax), none of which exist in this repo yet. Codex currently has no repo-level way to provide a child-specific `AGENTS.md` or disable tool schemas for spawned agents; the viable Codex work is to keep the normal installed `AGENTS.md` tiny (CX5), move detail to the `less-tokens` skill, avoid `fork_context=true` by default, and add a break-even warning to the skill.
- **G17 — Spawn/no-spawn decision rule** *(meta)* — a child costs a full fixed startup tax (system/developer prompt + instruction files + schemas); only spawn when the tokens the child discards exceed that tax. *Verdict: heuristic for a doc/skill, not hook-enforceable.* **Dual scope:** heuristic for both agents' skills, but the break-even constant differs. Codex rule of thumb: do not spawn for a single `rg`, one small file read, or a short test command; consider spawning only for independent exploration, noisy verification, or large-source summarization where the discarded transcript/logs would materially exceed a fresh child startup and the user asked for delegation/parallelism. **Claude side:** Claude's break-even is lower — children start cold (no transcript copy) and parallelize natively, so the startup tax is just system prompt + `CLAUDE.md` + schemas; still skip spawning for a single read/grep/short test.

### Decided against (record to prevent re-proposal)

- **F4 — Consolidate overlapping tools** *(meta)* — `search.py`/`search_config.py`/`symbols.py`/`parse.py` have distinct jobs (search runtime / config / symbol index / AST parse). Merging is pure refactor: zero token saving, real regression risk across both agents. Not worth it.
- **G10 — Bound subagent search breadth** *(input)* — the harness Explore agent already exposes a breadth knob (medium / very thorough); less_tokens adds nothing and cannot hook-enforce a sub-process's search scope. Owned by the harness, not this toolkit. Skip. **Dual scope:** Explore's breadth knob is a Claude harness feature. Codex has `agent_type="explorer"` but no repo-owned breadth knob; narrowness must come from the delegated prompt ("answer only X, inspect only paths matching Y"). Skip hook/config work for both — distinct reasons, recorded so neither agent re-proposes it.
- **S6 — Tiered effort** *(output)* — route tasks to Haiku/Sonnet/Opus via a tier matrix + flag. No hook can force a per-turn model downshift, so enforcement is weak and the claimed 50–70% saving is unverified. The shipped caveman Stop hook already captures output-token savings deterministically. Skip.
- **Graphify integration** *(input)* — evaluated 2026-07-04 (`eb_eval_4jul26.md`, `tect` review). Graphify's structural (AST) extraction is free, but its semantic extraction — the part that actually builds the knowledge graph — dispatches parallel Claude subagents that spend real input/output tokens unless a Gemini/Google API key is configured. Adopting the default build path means spending tokens to build the thing meant to save tokens: a direct inversion of this repo's mission, same reasoning already applied to reject the query/result cache (F4's neighbor ruling above — "saves embedding compute, not tokens"). The capability gap (cross-entity relationship queries, community/"god node" detection) is real but is a navigation feature, not a token-reduction lever, so it's out of scope for this repo's mission as specified. No artifact/state collision either way (`graphify-out/` doesn't touch `.claude/state/` or `.less_tokens/`) — the rejection is entirely economic. Skip. Reopen only if graphify ships a Gemini-only build mode this repo can hard-gate to, and only as an optional add-on for *host* repos this toolkit installs into, never for this repo's own dogfooding.

---

## Vector Search & Indexing

### High Priority

- **Same-session `search.py` repeated-query cache** *(input)* — reopened 2026-07-04
  (`eb_plan_4jul26.md` Strategy 5), correcting `DOCUMENTATION.md`'s prior "query/result cache"
  rejection: that ruling was about caching *embeddings* (compute, not tokens — still correctly
  rejected) and never actually distinguished the separate claim that skipping an *identical
  repeated `search.py` invocation* within a session would also skip its tool-output round-trip
  re-entering the transcript — a real, `basis="measured"` context-token saving, same shape as
  `context-cache-read`/`-grep`/`-bash`. **Instrumentation shipped 2026-07-05**:
  `_record_search_near_miss()` in `.claude/tools/search.py` appends a `kind: "search"` record to
  `near_misses.jsonl` whenever a query exactly repeats an earlier query in the same
  `resolve_session()` session (tracked via `state/search-session-cache.json`, capped at the last
  50 queries per session). Same fail-open, additive-only, never-blocks discipline as
  `context_cache.record_near_miss`. **Still do not implement the cache** — let this run and
  accumulate real `near_misses.jsonl` data first. If it shows repeats are rare, this stays
  periphery for a different, evidenced reason; if they're common, build the cache against that
  evidence.

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
