# Backlog

Canonical list of planned work not yet started. Work the **Ready now** table from top to bottom; do not start a blocked item until its unblock condition is met.

Priorities: **P0** = correctness or false-health reporting, **P1** = direct token savings or enforcement proof, **P2** = maintainability/documentation, **P3** = opportunistic. States: **Ready**, **Research** (time-boxed investigation with a decision as a valid outcome), **Blocked**, and **Later**.

Every item has a stable ID. When shipping one, cite `[ID]` in the `CHANGELOG.md` `[Unreleased]` entry and delete the item here before merging. See [.claude/skills/bug-hunt/SKILL.md](.claude/skills/bug-hunt/SKILL.md) and [.claude/skills/bug-hunt/bughuntlog.md](.claude/skills/bug-hunt/bughuntlog.md) for the bug-hunt protocol. Rejected or resolved proposals belong in [DECISIONS.md](DECISIONS.md), not here.

## Ready now

| Order | ID | Priority | Outcome | Depends on |
|---:|---|:---:|---|---|
| 1 | B2 | P0 | Make the parity audit reject stale/cwd-sensitive commands | — |
| 2 | CX16 | P0 | Give this repo a supported, idempotent Codex dogfood refresh | B2 |
| 3 | F1 | P1 | Remove test-command prose from always-loaded context | — |
| 4 | SA1 | P1 | Cap a subagent's return before it inflates the parent's transcript | — |
| 5 | SA2 | P1 | Log subagent fan-out telemetry (spawn/return size, cumulative absorption) | — |

- **B2 — Codex parity audit accepts stale relative hook commands** *(bug / verification)* — `.claude/tools/codex_parity_audit.py:45-47` treats any command containing `.codex/hooks/<script>` as wired; it does not validate the absolute launcher/script paths emitted by `install.py:806-831`. The source repo's stale generated `.codex/hooks.json` therefore passed most checks even though its relative commands fail outside the repo root. Compare installed entries with `build_codex_hook_entries()` and execute a representative command from a nested cwd. Acceptance: the observed stale file fails the audit and a current install passes.

- **CX16 — Make Codex dogfood installs self-diagnosing and recoverable** *(meta / install parity)* — This repo's generated, ignored `.codex/` layer can silently lag the checked-in manifest, while `install.py` refuses to target the source directory itself. Provide a supported refresh path for the source repo and make skipped or unwritable hook installation an explicit degraded result. Acceptance: starting from the observed stale state, one documented command installs every required script and manifest entry with absolute paths; the parity audit reports zero unwired rows; representative wrappers run from a nested cwd; a second refresh is a no-op.

- **F1 — Replace always-loaded test command prose with a dev command shim** *(fixed / prose-to-code)* — `CLAUDE.md:20-31` stores install/test commands and CI matrix prose in always-loaded context, while `pyproject.toml:1-3` and workflows already encode pytest paths. Add a small `.claude/tools/dev.py` or `tools/check.py` command (`unit`, `integration`, `all`, `single <nodeid>`) that uses the configured venv and pytest paths, then shrink `CLAUDE.md` to the command plus a documentation pointer. Acceptance: local and CI test paths share one source and the multi-line command block leaves `CLAUDE.md`.

- **SA1 — Cap a subagent's return before it inflates the parent's transcript** *(hook / subagent)* — No hook fires on the `Task` tool today; confirmed by grep of `agents/common/hooks/hook_manifest.py`, the only hook that fires on a subagent boundary at all is `SubagentStop` (shared wiring with `Stop`, used only for the terse-output nudge and the savings-html regen). A parent orchestrator running several subagents absorbs each one's full final response verbatim into its own transcript. Add a `PostToolUse:Task` hook that digests a subagent's return before it lands in the parent's transcript: reuse `truncate_output.py`'s char-ceiling head/tail elision for the size ceiling, but add new pass/fail/blocker-style field extraction, since subagent prose isn't log-shaped like Bash output and a naive tail-cut risks eating the actual recommendation. Acceptance: an oversized subagent return is capped before the parent's next turn resumes; the extracted pass/fail/blocker summary (or head+tail + omission marker as fallback) is preserved; a representative multi-agent run shows a measurable per-child token reduction. Cost-benefit: Low-Med build cost, low regression risk (additive hook, no existing matcher touched), `[HYP]` savings but High directional confidence — see `reports/runs/2026-07-16-less-tokens-subagent-strategies/report.md` (ever_better team engagement, ranked #1 of 5, "build now").

- **SA2 — Log subagent fan-out telemetry** *(measurement / subagent)* — No event category exists for the cost of spawning subagents; every other subagent-strategy candidate in this backlog is currently a `[HYP]` claim, not a measured one, because there is no baseline. Add a `subagent_fanout` event to `state/savings.jsonl` at `PreToolUse:Task`/`PostToolUse:Task`: spawn count, per-child prompt size, per-child return size, cumulative parent-side absorption. Surface a rollup in the existing savings report distinct from generic Bash/Read totals. Acceptance: a multi-subagent session produces one `subagent_fanout` event per spawn with accurate kept/elided-equivalent figures, and the savings report shows a distinct subagent-fanout line. Cost-benefit: Low-Med build cost, near-zero regression risk (no existing hook logic touched), zero direct token savings itself but it's the only mechanism that turns SA3/SA4/SA5's benefit claims from `[HYP]` into `[OBS]` — see `reports/runs/2026-07-16-less-tokens-subagent-strategies/report.md`, ranked #2, "build now, paired with SA1."

## Next

Start these after the P0 Codex foundation above. Research items are bounded spikes: implementation is preferred, but a verified platform limitation recorded in `DECISIONS.md` is also a complete outcome.

| Order | ID | Priority | State | Outcome | Depends on |
|---:|---|:---:|---|---|---|
| 6 | CX17 | P1 | Research | Prove whether Codex replaces tool output before model context | CX16 |
| 7 | CX18 | P1 | Research | Find a real Codex end-of-turn enforcement surface | CX16 |
| 8 | CX19 | P1 | Ready | Replace synthetic hook smoke tests with semantic fixtures | CX17, CX18 captures |
| 9 | D1 | P2 | Ready | Add recovery guidance for common install/index failures | — |
| 10 | P4 | P2 | Ready | Generate installer flag docs from parser metadata | — |
| 11 | A1 | P2 | Ready | Generate shared subagent guidance once | — |
| 12 | P5 | P2 | Ready | Enforce canonical homes for root documentation | — |
| 13 | D2 | P2 | Ready | Publish one merge-safe hook configuration example | — |
| 14 | D3 | P2 | Ready | Explain search-window and exclusion configuration | — |
| 15 | D4 | P2 | Ready | Publish reproducible real-codebase savings benchmarks | P0 foundation |
| 16 | D6 | P2 | Ready | Delete each root `*plan.md` once its content is fully implemented | — |
| 17 | CX20 | P2 | Research | Determine whether Codex can initiate compaction | CX16 |

- **CX17 — Prove and, if supported, implement real Codex tool-output replacement** *(tool / enforcement parity)* — `agents/codex/hooks/truncate-output.py:65-92` prints the shortened result and returns the shared hook code, but no live test proves that this replaces the original tool result before the model receives it. Capture real oversized Bash and filesystem-read payloads and inspect the next model-visible context. If Codex exposes a replacement contract, implement and regression-test it. Otherwise document the platform blocker, stop labeling Codex truncation savings as measured, and downgrade the parity row. Acceptance: an oversized sentinel present only beyond the cap cannot be recovered from the next Codex turn, while the head/tail and omission marker remain available—or the unsupported claim is removed everywhere.

- **CX18 — Codex final-response enforcement needs a real end-of-turn contract** *(output / enforcement parity)* — `hook_manifest.py:148-168` substitutes `PostToolUse .*` for Claude's `Stop|SubagentStop`, while `agents/codex/hooks/terse-reminder.py:24-42` expects a top-level `response` field that ordinary PostToolUse payloads may not contain. Capture tool-using, tool-free, and subagent-final turns; then wire a real turn-complete surface if one exists. Acceptance: tool-free and tool-using over-budget responses trigger the check, concise responses do not loop, subagent behavior is explicit, and savings refresh once per turn—or docs/parity clearly classify the feature as advisory.

- **CX19 — Replace synthetic Codex hook smoke coverage with semantic, versioned payload coverage** *(meta / reliability)* — `.claude/tests/unit/test_codex_event_contract.py:49-169` invents payloads and accepts any exit code in `{0, 2}` if there is no traceback; unexpected payloads can therefore no-op silently. Store sanitized fixtures for supported Codex versions covering reads, searches, Bash, apply_patch, Edit/Write, tool errors, available final-response events, and unknown MCP tools. Assert semantic outcomes, not non-crash. Acceptance: every supported matcher has a real-shape fixture and outcome assertion; unknown shapes fail open with bounded schema-only telemetry; schema drift creates a targeted failure or audit warning.

- **D1 — Add a troubleshooting section** *(documentation / recovery)* — Cover the common failures currently requiring source inspection: first-run model download failure, wrong venv path, empty or stale indexes, background refresh failures and `.claude/state/index-refresh.log`, and what an empty search result does to the search-first gate. Acceptance: each symptom has a check, likely cause, and recovery command.

- **P4 — Generate installer flag docs from argparse metadata** *(prose-to-code / doc drift)* — `DOCUMENTATION.md:37-51` hand-lists optional flags while `install.py:1930-1996` is authoritative. Render an `<!-- installer-flags -->` block from parser metadata or a shared registry. Acceptance: every public flag is documented unless explicitly hidden and CI catches drift.

- **A1 — Split shared subagent guidance from platform mechanics** *(architecture / divergent prose)* — Claude and Codex skills duplicate the output contract, prompt shape, noisy-verification pattern, and large-source digest guidance; only their agent/tool mechanics differ. Factor the shared contract into one generated source while keeping explicit platform-specific rules. Acceptance: return-shape and "do not paste" edits happen once and both installed skills retain their divergent mechanics. Note: this is a docs-dedup item about existing subagent-usage *guidance text*, distinct from SA1/SA2/SA3/SA4/SA5's runtime hook work on the `Task` tool itself.

- **P5 — Code the root-document canonical-home rules** *(meta / prose-to-code)* — The claudemd skill carries a hand-maintained topic-home table and asks agents to find duplicates manually. Move the mapping into structured config consumed by `claudemd_audit.py --docs` or a dedicated gate. Acceptance: the skill points to the gate and CI/release checks report non-canonical duplicate sections with file:line references.

- **D2 — Replace fragmented hook JSON with one merge-safe example** *(documentation / installability)* — `DOCUMENTATION.md:343-397` shows a base settings object followed by detached optional matcher fragments, leaving users to infer event placement and JSON merging. Generate or publish one valid, unified configuration and explain which file the installer owns. Acceptance: the example can be copied as valid JSON and includes the default hook set in correct event order.

- **D3 — Explain search-window and exclusion configuration** *(documentation / precision)* — The configuration table names `EXCLUDED_DIR_NAMES`, `EXCLUDED_DIR_PREFIXES`, and the 300-second search window but does not explain their behavioral differences or where to tune `WINDOW_SECONDS`. Acceptance: examples distinguish name-based from prefix-based exclusions and show how the gate window is configured.

- **D4 — Publish reproducible token-savings benchmarks** *(evidence / documentation)* — Measure the shipped strategies on a representative real codebase, including method, workload, baseline, variance, and agent/platform limits. Acceptance: another maintainer can rerun the benchmark and reproduce the report within stated tolerance; unverified savings claims are labeled as estimates.

- **D6 — Delete each root `*plan.md` once its content is fully implemented** *(hygiene / doc lifecycle)* — Root planning docs (`stats_plan.md`, `HTML_DOCUMENTATION_PLAN.md`) are working documents, not canon — once everything they describe has shipped, a stale copy left in the repo root is dead weight competing with `CHANGELOG.md`/`DOCUMENTATION.md` as a source of truth. Audit each existing `*plan.md` against current `CHANGELOG.md`/`DECISIONS.md` and the shipped code; delete (`git rm`) any plan whose described work is fully implemented, first extracting any still-open item into its own `BACKLOG.md` row so no undone work is silently lost. Apply the same check whenever a future `*plan.md` is added. Acceptance: `stats_plan.md` and `HTML_DOCUMENTATION_PLAN.md` are each either deleted with their remaining open items captured as new backlog rows, or left in place with the specific unimplemented section cited as the reason.

- **CX20 — Codex compaction remains a nudge, not control parity** *(input / platform gap)* — Investigate whether the current Codex app exposes a compaction or session-rollover API. If available, invoke it and verify transcript size before recording measured savings. Otherwise keep the nudge, test hysteresis on live transcript paths, and record the limitation. Acceptance: either an oversized live session is compacted automatically with honest before/after telemetry, or docs/parity/telemetry consistently say Codex only receives an advisory nudge.

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
