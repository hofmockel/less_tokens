# Backlog

Canonical list of planned work not yet started. Work the **Ready now** table from top to bottom; do not start a blocked item until its unblock condition is met.

Priorities: **P0** = correctness or false-health reporting, **P1** = direct token savings or enforcement proof, **P2** = maintainability/documentation, **P3** = opportunistic. States: **Ready**, **Research** (time-boxed investigation with a decision as a valid outcome), **Blocked**, and **Later**.

Every item has a stable ID. When shipping one, cite `[ID]` in the `CHANGELOG.md` `[Unreleased]` entry and delete the item here before merging. See [.claude/skills/bug-hunt/SKILL.md](.claude/skills/bug-hunt/SKILL.md) and [.claude/skills/bug-hunt/bughuntlog.md](.claude/skills/bug-hunt/bughuntlog.md) for the bug-hunt protocol, and [.claude/skills/bugfix/SKILL.md](.claude/skills/bugfix/SKILL.md) for the bugfix protocol. Rejected or resolved proposals belong in [DECISIONS.md](DECISIONS.md), not here.

## Ready now

| Order | ID | Priority | State | Outcome | Depends on |
|---:|---|:---:|---|---|---|

## Next

Research items are bounded spikes: implementation is preferred, but a verified platform limitation recorded in `DECISIONS.md` is also a complete outcome.

| Order | ID | Priority | State | Outcome | Depends on |
|---:|---|:---:|---|---|---|

## Blocked / evidence collection

Do not implement these yet. Satisfy the unblock condition, then move the item into **Ready now** at the appropriate order.

| ID | Priority | Blocked on | Unblock signal |
|---|:---:|---|---|
| C1 | P1 | CX16 and a real Codex observation window | Genuine bash/grep near-misses show repeatable normalization candidates |
| SA3 | P2 | SA2 | Fan-out telemetry shows input-side (spawn-context) waste is a meaningful share of subagent cost |
| SA4 | P2 | SA2 | Fan-out telemetry (plus a live `Task`-hook payload capture) shows concurrent subagent budget contention is common enough to matter |
| SA5 | P2 | SA2 | Fan-out telemetry shows truncation needs differ enough by subagent type to justify per-role rules over SA1's generic cap |

- **C1 — Widen cache keys for bash/grep and split TTLs** *(input / cache)* — Exact literal keys prevent semantically identical calls from hitting, but current Codex telemetry contains no genuine bash/grep observations because the dogfood install drifted stale. After CX16, collect a real data window; normalize only output-shape-neutral flags observed in near-misses, key grep on normalized `(pattern, path, glob, type)`, and expose `CONTEXT_CACHE_BASH_TTL` separately. `eb_telemetry_9jul26.md` §2 provides Claude-side examples but does not satisfy the Codex evidence requirement. Acceptance: the normalization allowlist is justified by captured cases, equivalent calls hit, meaning-changing calls miss, and bash/grep TTLs are independently configurable.

- **SA3 — Filter what a parent hands a subagent at spawn time** *(hook / subagent)* — Add a `PreToolUse:Task` hook applying search-first-style filtering to the prompt/description handed to a spawned subagent: strip full file dumps the parent already read in favor of paths + line ranges, let the subagent re-fetch via its own guarded `Read`. Moderate risk — over-filtering can break what the subagent actually needs to do its job, a correctness risk, not just a perf one. Do not build ahead of SA2: whether input-side (spawn context) or return-side (SA1) waste dominates is currently unknown, and building this first means guessing which side of the pipe matters. Acceptance: SA2 telemetry shows spawn-context size is a meaningful share of total subagent cost; the filter then measurably shrinks prompt-side tokens without a regression in subagent task success rate. Cost-benefit: Med build cost, `[HYP]` Med-confidence benefit — see `reports/runs/2026-07-16-less-tokens-subagent-strategies/report.md`, ranked #3, "wait for telemetry."

- **SA4 — Verify per-subagent session-id exposure and, if confirmed, scope budget state per subagent** *(research → hook / subagent)* — Budget control-plane state is keyed only by the literal `"claude"`/`"codex"` agent string (`agents/common/budget/state.py:27-28`) — one shared file across every concurrently active subagent, so a parent and its subagents can race on it (atomic tmp+rename write means no corruption, but last-write-wins data loss is possible). `BudgetEvent` already carries `session_id`/`run_id` per event, so rekeying state by session id is mechanically straightforward *if* a subagent's `Task`-hook payload actually exposes a session id distinct from its parent's — that is currently unverified. This is the highest-cost, highest-regression-risk candidate of the subagent-strategy set (it touches shared state every existing single-agent install depends on), and its true cost is unknown until the payload question is answered — capture a live `Task` hook payload first (a cheap check, not a build) before committing to the state-rekeying design. Acceptance: either a live payload confirms a distinct per-subagent session id and budget state is rekeyed with a passing concurrency test (two simultaneous subagents don't clobber each other's budget), or the payload does not expose one and that platform limitation is documented in `DECISIONS.md` and this item downgrades to **Later**. Cost-benefit: High build cost plus a hidden cost (the unverified unknown itself), benefit is a correctness/fairness fix, not token savings — see `reports/runs/2026-07-16-less-tokens-subagent-strategies/report.md`, ranked #4, "not worth building yet."

- **SA5 — Subagent-type-aware truncation policy** *(hook / subagent, refinement)* — Key SA1's digest policy off the subagent's declared role (`subagent_type`, e.g. a `qa` result keeps failure lines + counts and drops passing-test noise; a `tect` result keeps recommendation + confidence and drops the evidence appendix) instead of one generic shape. Carries an ongoing maintenance burden — role-keyed rules rot as the subagent roster changes, similar upkeep cost to a linter ruleset. Do not build until SA2 telemetry shows type-specific waste differs enough from SA1's generic cap to justify it; may be parked indefinitely if SA1 alone proves sufficient. Acceptance: telemetry shows a measurable gap between generic-cap and type-aware savings for at least two distinct subagent types, and the resulting rule set is captured in versioned config, not inline conditionals. Cost-benefit: Med-High build cost plus rule-rot maintenance, `[HYP]` unproven benefit — see `reports/runs/2026-07-16-less-tokens-subagent-strategies/report.md`, ranked #5, "not worth building yet, possibly park indefinitely."

## Later

| ID | Priority | Why later |
|---|:---:|---|
| DX1 | P3 | Process improvement; no direct runtime saving |
| D5 | P3 | Marketing aid after core documentation is reliable |
| DX2 | P3 | Infrastructure cost only matters if perf variance becomes a problem |
| SA6 | P3 | Speculative — contingent on harness/`Task`-tool internals outside less_tokens' control |

- **DX1 — Add same-pattern propagation to the bugfix skill** *(process)* — After a bug fix, require a codebase-wide search for the root-cause construct and create backlog items for additional hits. Acceptance: `.claude/skills/bugfix/SKILL.md` contains the explicit search-and-record step.

- **D5 — Create an animated before/after demo** *(documentation / adoption)* — Show a full read versus targeted search after the troubleshooting and configuration documentation is stable.

- **DX2 — Consider a self-hosted runner for perf** *(infrastructure)* — The perf job downloads a roughly 130 MB embedding model and inherits hosted-runner CPU variance. Revisit only if cold-cache time or variance causes material delays or false failures; weigh that against runner maintenance and security.

- **SA6 — SubagentStop digest-and-discard for replayed child transcripts** *(hook / subagent, speculative)* — If a future harness path surfaces a spawned subagent's full transcript back to the parent for replay (Claude Code does not do this by default today), write a compact digest artifact at `SubagentStop` and never let raw transcript content flow back. Not actionable now — there is no confirmed mechanism to hook. Revisit only if the harness's `Task`-result surfacing changes. — `reports/runs/2026-07-16-less-tokens-subagent-strategies/report.md`, ranked #6, "parked."
