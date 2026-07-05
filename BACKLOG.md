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
- **G7 — Subagent context re-derivation** *(input)* — parent writes a compact context pack (relevant slices + search hits) to `STATE_DIR`; spawned agents read that instead of re-reading/re-searching cold. Discipline + helper skill; hard to hook-enforce. *Verdict: defer — spiky, only pays when subagents run heavily.* **Codex viability:** viable as a user-authorized `multi_agent_v1.spawn_agent` workflow, not as automatic repo behavior. The context pack must be pointer-heavy (`path:line`, search query, command to run) because passing full text in the spawn prompt pays parent-output + child-input tokens.

> **Dual-scope contract (G-series subagents).** Hook-enforced levers land in `agents/common/`, wire into **both** `.claude/settings.json` (matchers `Read|Grep|Glob|Edit|Write|Bash`) and `.codex/hooks.json` (broad `mcp__filesystem__.*` + `apply_patch`, `LESS_TOKENS_AGENT=codex`, `.less_tokens/tools/` shims), and get a row in `agents/common/hooks/parity.json`. Prompt/skill levers land in **both** the Claude skill + `CLAUDE.md` and the Codex `less-tokens` skill + `AGENTS.md`. Respect the wall: `agent_overrides.claude` in `budget.json` is Claude-only by construction. **Codex answer:** Codex exposes `multi_agent_v1.spawn_agent`, `wait_agent`, `send_input`, and `close_agent`, but the tool contract says not to spawn unless the user explicitly asks for subagents, delegation, or parallel agent work. Therefore less_tokens must not sell Codex subagents as autonomous token control; implement them as opt-in skill guidance/templates. The spawn tool is product surface, not an installed project artifact, so CI can test prompt templates and installed hook cwd resolution, but cannot prove real Codex child inheritance end-to-end. **Claude-side ground truth (`.claude/settings.json`):** a Claude child's tool calls *do* fire `PreToolUse`/`PostToolUse`, so search-first, auto-slice, grep-first, read-guard, context-cache, truncate-output compound inside it automatically. But caveman + savings-html are wired only under **`Stop`**, and a subagent emits **`SubagentStop`** (unwired) — so output/terse + savings levers do **not** reach a Claude child until `SubagentStop` is added. `CLAUDE.md` loads once per session: the per-child fixed lever is an agent-definition file (`.claude/agents/<name>.md`) system prompt + `tools:` allowlist, not a slimmer `CLAUDE.md` (none exist yet). Claude Agent-tool children start cold — the native equivalent of Codex `fork_context=false`.

- **G8 — Parallel subagent dispatch** *(meta)* — spawn independent subtasks concurrently so each keeps a small context instead of one bloated parent thread; same wall-clock. No helper/skill today. *Verdict: discipline-only, not hook-enforceable; worth a thin skill if subagent use grows.* **Dual scope:** Claude uses its Agent tool. Codex can use `multi_agent_v1.spawn_agent` only after explicit user authorization; prefer `agent_type="explorer"` for specific read-only code questions and `agent_type="worker"` only with disjoint file ownership. Default `fork_context=false` to avoid copying the parent transcript unless the child truly needs prior conversation. Heuristic lives in both agents' skills; startup-tax math differs (Claude system prompt + `CLAUDE.md` + tool schemas vs Codex system/developer stack + `AGENTS.md` + callable tool schemas). **Claude side:** the Agent tool is present today and its children start cold + parallelize natively (the `fork_context=false` default), so build the dispatch helper now without gating on Codex.
- **G9 — Output contracts for subagents** *(input)* — parent prompt template pins exactly what the agent returns ("file:line list, no code") so the final message stays small. Ship as a prompt snippet/skill; no enforcement hook possible. *Verdict: low cost, marginal until subagents run often.* **Dual scope:** in-child terse-output does *not* even run on a Claude child — caveman is a `Stop` hook and a subagent emits `SubagentStop` (unwired), so wire caveman to `SubagentStop` or the return contract is prompt-only. Codex children should be prompted for `files changed`, `findings`, `verification`, and `blockers` only, with line references and no pasted file bodies/logs. Encode this in both the Claude subagent prompt and the Codex `less-tokens` skill.
- **G11 — Isolate noisy verification in a subagent** *(tool)* — run test/lint/build loops inside a spawned agent; failures, retries, stack traces stay in its window, parent gets pass/fail + summary. Complements `lean-output` (which trims in-context) by moving the whole loop out of the parent. *Verdict: real tool-bucket win when verification is noisy; needs a skill, no hook.* **Dual scope:** the in-child trim reuses `lean-output` (shipped both, parity.json). Codex viability is opt-in only; delegate verification when it can run while the parent continues non-overlapping work, otherwise the child startup tax plus waiting can cost more than a lean local command. **Claude side:** the verification child works today via the Agent tool; `lean-output` trims inside it through `PostToolUse`, which *does* fire in Claude children.
- **G12 — Summarize-then-discard large reads via subagent** *(input)* — agent ingests a big doc/log and returns a digest; the source never enters the parent. Complements auto-slice/truncation (in-context) by pushing the full read across the agent boundary. *Verdict: useful for one-off large sources; discipline/skill, not hook-enforceable.* **Dual scope:** write the digest to `.less_tokens/state/` (shared path) in an agent-neutral format, so a Codex child and a Claude parent (or vice versa) interoperate. For Codex, pass `fork_context=false` and a pointer to the source; require the return to include digest path + source path + enough line refs to verify, not the original payload. **Claude side:** a Claude child returns the digest directly in its Agent-tool return message — no `.less_tokens/state/` file needed; that shared file is the Codex / cross-agent path only, so don't force Claude through the indirection.
- **G13 — Pointer-not-payload spawn prompts** *(input)* — pass `path:line` + a search query in the spawn prompt instead of pasted files; the child's search-first fetches only what it needs. Avoids double-billing the same bytes as parent output then child input. *Verdict: prompt discipline/skill; pairs with G7.* **Dual scope:** prompt discipline in both agents' skills; pointers resolve via search-first, which already ships for both (parity.json), so no new hook. Codex-specific template should include: `fork_context=false unless needed`, `use .less_tokens/bin/python .less_tokens/tools/search.py`, `return only file:line findings`, and `close_agent after result`. **Claude side:** a cold Claude child has no recent-search state, so search-first *blocks* its first Read of a bare `path:line` — the pointer must carry the query and the child must search first, or the gate adds a round-trip instead of saving one.
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
  `context-cache-read`/`-grep`/`-bash`. Not yet built or measured either way. **Do not implement
  the cache yet** — first add near-miss instrumentation to `search.py`'s query path (same
  `near_misses.jsonl` mechanism already shipped for cached-bash/cached-grep/compaction-threshold,
  see `agents/common/hooks/context_cache.py`'s `record_near_miss`) to find out how often an
  identical query is actually repeated within a session before building anything. If the real
  data shows repeats are rare, this stays periphery for a different, evidenced reason; if they're
  common, build the cache against that evidence.

---

## Installer

### High Priority

---

## Hooks & Caveman Mode

- **context-cache trusts mtime as proof of "unchanged"** *(tool / correctness)* — `check_read` ([agents/common/hooks/context_cache.py:88-97](agents/common/hooks/context_cache.py)) blocks a re-Read when `Path(file_path).stat().st_mtime` equals the recorded mtime, and the block message asserts "file unchanged. Skip this Read; content is still valid in context." mtime equality is **not** content equality: coarse filesystem mtime granularity, mtime-preserving writes (`cp -p`, `git checkout`/revert, `rsync --times`, editors that restore mtime), or clock skew can change the bytes while leaving mtime untouched. The hook then tells the agent stale content is current — and any `Edit` built on that cached view matches against the wrong text, silently. Likelihood is low and the upside (token saving) is real, but the failure mode lands on **edit correctness**, not just tokens, and is invisible when it happens. *Fix options, cheapest first: (a) add `st_size` to the cache entry + comparison (one extra field, catches most same-mtime content changes); (b) soften the message from "file unchanged" to "likely unchanged — re-read if you need exact bytes"; (c) key on a content hash for full correctness (most expensive, defeats some of the saving). Observed 2026-06-26 — fell back to `cat` to get exact strings for an Edit because the Read was cache-blocked.*

---

## Prose to Code

Rules, protocols, and configs expressed as natural language that could be deterministic scripts, structured data, or shorter pointers. Ordered by per-turn impact.

### High Priority

### Medium Priority

---

## README Accuracy

### Inaccurate

- **README says `/def` lookup is installed user-facing behavior** *(docs / correctness)* — [README.md:30](README.md) advertises "exact `/def` lookup for Python and JS/TS symbols," but installer deployment does not include `.claude/commands/` today. Source has `.claude/commands/def.md`, but `_install_specs()` deploys `.less_tokens/config`, `.less_tokens/tools`, shared budget hooks, `.claude/tools`, `.claude/schema`, `.claude/skills/claudemd`, and selected hooks/skills only; no commands directory is copied. Fix either the implementation (install `.claude/commands/{def,search,build-index}.md`) or the README wording (say `symbols.py` lookup, with `/def` only when commands are installed). Acceptance: README, DOCUMENTATION.md command layout, installer specs, and tests agree on whether slash commands are installed.

- **README implies Codex hooks are always wired by default** *(docs / correctness)* — [README.md:38](README.md) says core hooks are wired by default for the selected agent, but Codex hook wiring is conditional on `.codex/` being writable. If not writable, install skips `.codex/hooks.json` and installs only `AGENTS.md` + skills. Fix wording to "wired by default when the target hook location is writable; Codex remains best-effort." Acceptance: README quick-start text matches `install.py` behavior and DOCUMENTATION.md's Codex best-effort caveat.

- **README mischaracterizes Codex install artifacts as only adapter hooks plus `AGENTS.md`** *(docs / correctness)* — [README.md:93](README.md) says Claude artifacts land under `.claude/`, shared budget under `.less_tokens/`, and Codex adds adapter hooks plus `AGENTS.md`. In reality, even Codex installs deploy `.claude/tools/`, `.claude/schema/`, `.claude/skills/claudemd`, and use `.claude/index.db` as the shared index; `.less_tokens/tools/*.py` are shims to the `.claude/tools` implementation. Fix README to explain that `.claude/` contains shared implementation/index artifacts, not only Claude-agent artifacts. Acceptance: README quick-start artifact summary matches DOCUMENTATION.md "Codex support" and installer copy steps.

### Language / Precision

- **README compaction row says `/compact` for both agents** *(docs / precision)* — [README.md:35](README.md) says the PostToolUse hook nudges `/compact` when the transcript grows large. That is precise for Claude, but Codex has no Claude slash-command path and `agents/codex/hooks/compact-trigger.py` tells the user to start a fresh or compacted Codex session. Fix the row to split agent behavior: Claude nudges `/compact` or fresh session; Codex nudges fresh/compacted Codex session. Acceptance: no README prose implies Codex can run Claude's `/compact` command.

---

## Claude Agent

Claude-only token savings. Isolation walls: `agent_overrides.claude` in `.less_tokens/config/budget.json` (deep-merged per-agent at `agents/common/budget/config.py:82-84`, so Codex never sees it) and `.claude/settings.json` hook wiring (separate file from `.codex/hooks.json`). Touch only those and Codex is unaffected by construction.

### High Priority

### Medium Priority

---

## Codex Agent

### High Priority

- **CX12 — Codex delegated-work prompt templates** *(input/tool/meta)* — Add a short, optional section to `agents/codex/skills/less-tokens/SKILL.md` for user-authorized `multi_agent_v1.spawn_agent` use. It should cover the Codex-specific constraints discovered during backlog review: spawn only when the user asks for delegation/parallelism; default `fork_context=false`; pass pointers/search commands instead of pasted files; choose `explorer` for specific read-only questions and `worker` only with disjoint write ownership; tell workers not to revert unrelated edits; require compact returns (`files changed`, `findings`, `verification`, `blockers`); close completed agents. Acceptance: skill text stays small enough that `AGENTS.md` only points to it, and examples avoid full payloads.

- **CX13 — Codex hook inheritance smoke check for nested cwd** *(meta / correctness)* — Add an install/check test or diagnostic that runs representative Codex hook wrappers from a nested project directory and proves they resolve repo root, `.less_tokens/bin/python`, `.less_tokens/tools/`, `.codex/hooks/`, and `LESS_TOKENS_AGENT=codex` correctly. This does not prove product-level `spawn_agent` inheritance, but it covers the part less_tokens owns and reduces G15 risk. Acceptance: failures are actionable ("hooks.json missing", "wrapper cannot import payload", "venv launcher missing") and do not require a live Codex subagent in CI.

### Medium Priority

- **CX14 — Document Codex subagent support boundary** *(meta / docs)* — Update `DOCUMENTATION.md` near the Codex best-effort hook section to say Codex subagents are available through the app's `multi_agent_v1` tool surface, not installed by less_tokens, and may only be used when the user explicitly asks for delegation/parallelism. State that `.codex/hooks.json` cannot intercept arbitrary parent reasoning and re-route it into a child; less_tokens can only provide prompt templates, installed tools, hook wrappers, and smoke checks. Acceptance: avoids claims of automatic Codex subagent token savings.

### Low Priority

- **CX15 — Measure Codex spawn break-even manually** *(fixed/meta)* — Once CX12 exists, run a small manual benchmark in Codex app: one parent-only exploration, one `fork_context=false` explorer, and one `fork_context=true` explorer over the same task. Record approximate transcript/tool-output deltas and update the skill's spawn/no-spawn rule if the fixed startup tax is larger than expected. Keep this manual unless Codex exposes token/accounting telemetry for subagents.

---

## Developer Experience

### Low Priority

- **Bugfix skill: add same-pattern propagation step** *(process)* — After fixing any bug, require a codebase-wide search for the same pattern before closing. Add explicit checklist step to `.claude/skills/bugfix/SKILL.md`: grep for the root-cause construct (e.g. `endswith`, `offset`) across all `.py` files; open a backlog row for each additional hit. Prevents `endswith` and `offset=0` class of duplicates.

- **Consider GitHub self-hosted runners for the perf job** — the `perf` CI job downloads the fastembed model (~130 MB `BAAI/bge-small-en-v1.5`) and relies on `actions/cache`; a cold cache miss adds wall-clock time and network variance to timing results. A self-hosted runner with the model pre-installed in `~/.cache/huggingface` would remove both and give stable CPU baselines. Trade-off: infra maintenance + runner registration; only worth it if perf run times become a bottleneck or variance produces false failures. (Demoted: not on the token-reduction mission.)

---
