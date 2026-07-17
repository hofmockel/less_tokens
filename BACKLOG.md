# Backlog

Canonical list of planned work not yet started. Work the **Ready now** table from top to bottom; do not start a blocked item until its unblock condition is met.

Priorities: **P0** = correctness or false-health reporting, **P1** = direct token savings or enforcement proof, **P2** = maintainability/documentation, **P3** = opportunistic. States: **Ready**, **Research** (time-boxed investigation with a decision as a valid outcome), **Blocked**, and **Later**.

Every item has a stable ID. When shipping one, cite `[ID]` in the `CHANGELOG.md` `[Unreleased]` entry and delete the item here before merging. See [.claude/skills/bug-hunt/SKILL.md](.claude/skills/bug-hunt/SKILL.md) and [.claude/skills/bug-hunt/bughuntlog.md](.claude/skills/bug-hunt/bughuntlog.md) for the bug-hunt protocol. Rejected or resolved proposals belong in [DECISIONS.md](DECISIONS.md), not here.

## Ready now

| Order | ID | Priority | Outcome | Depends on |
|---:|---|:---:|---|---|
| 1 | B1 | P0 | Make the Codex truncation install smoke exercise real truncation | — |
| 2 | CX16 | P0 | Give this repo a supported, idempotent Codex dogfood refresh | B1 |
| 3 | F1 | P1 | Remove test-command prose from always-loaded context | — |

- **B1 — Codex truncation install smoke is a false positive** *(bug / verification)* — `install.py:1701-1715` invokes `truncate-output.py` with a small `"tool_output"` payload, but `agents/common/hooks/payload.py:73-78` only normalizes `tool_response` or `tool_result`. The adapter sees an empty result and exits 0 without exercising truncation, so `install.py --check --agent codex` can report wrapper health while output parsing/replacement is broken. Use a recognized output key and oversized content, then assert the cap, omission marker, and expected hook result rather than process startup. Acceptance: a regression test fails if the smoke payload is not actually truncated.

- **CX16 — Make Codex dogfood installs self-diagnosing and recoverable** *(meta / install parity)* — This repo's generated, ignored `.codex/` layer can silently lag the checked-in manifest, while `install.py` refuses to target the source directory itself. Provide a supported refresh path for the source repo and make skipped or unwritable hook installation an explicit degraded result. Acceptance: starting from the observed stale state, one documented command installs every required script and manifest entry with absolute paths; the parity audit reports zero unwired rows; representative wrappers run from a nested cwd; a second refresh is a no-op.

- **F1 — Replace always-loaded test command prose with a dev command shim** *(fixed / prose-to-code)* — `CLAUDE.md:20-31` stores install/test commands and CI matrix prose in always-loaded context, while `pyproject.toml:1-3` and workflows already encode pytest paths. Add a small `.claude/tools/dev.py` or `tools/check.py` command (`unit`, `integration`, `all`, `single <nodeid>`) that uses the configured venv and pytest paths, then shrink `CLAUDE.md` to the command plus a documentation pointer. Acceptance: local and CI test paths share one source and the multi-line command block leaves `CLAUDE.md`.

## Next

Start these after the P0 Codex foundation above. Research items are bounded spikes: implementation is preferred, but a verified platform limitation recorded in `DECISIONS.md` is also a complete outcome.

| Order | ID | Priority | State | Outcome | Depends on |
|---:|---|:---:|---|---|---|
| 4 | CX17 | P1 | Research | Prove whether Codex replaces tool output before model context | CX16 |
| 5 | CX18 | P1 | Research | Find a real Codex end-of-turn enforcement surface | CX16 |
| 6 | CX19 | P1 | Ready | Replace synthetic hook smoke tests with semantic fixtures | CX17, CX18 captures |
| 7 | D1 | P2 | Ready | Add recovery guidance for common install/index failures | — |
| 8 | P4 | P2 | Ready | Generate installer flag docs from parser metadata | — |
| 9 | A1 | P2 | Ready | Generate shared subagent guidance once | — |
| 10 | P5 | P2 | Ready | Enforce canonical homes for root documentation | — |
| 11 | D2 | P2 | Ready | Publish one merge-safe hook configuration example | — |
| 12 | D3 | P2 | Ready | Explain search-window and exclusion configuration | — |
| 13 | D4 | P2 | Ready | Publish reproducible real-codebase savings benchmarks | P0 foundation |
| 14 | CX20 | P2 | Research | Determine whether Codex can initiate compaction | CX16 |

- **CX17 — Prove and, if supported, implement real Codex tool-output replacement** *(tool / enforcement parity)* — `agents/codex/hooks/truncate-output.py:65-92` prints the shortened result and returns the shared hook code, but no live test proves that this replaces the original tool result before the model receives it. Capture real oversized Bash and filesystem-read payloads and inspect the next model-visible context. If Codex exposes a replacement contract, implement and regression-test it. Otherwise document the platform blocker, stop labeling Codex truncation savings as measured, and downgrade the parity row. Acceptance: an oversized sentinel present only beyond the cap cannot be recovered from the next Codex turn, while the head/tail and omission marker remain available—or the unsupported claim is removed everywhere.

- **CX18 — Codex final-response enforcement needs a real end-of-turn contract** *(output / enforcement parity)* — `hook_manifest.py:148-168` substitutes `PostToolUse .*` for Claude's `Stop|SubagentStop`, while `agents/codex/hooks/terse-reminder.py:24-42` expects a top-level `response` field that ordinary PostToolUse payloads may not contain. Capture tool-using, tool-free, and subagent-final turns; then wire a real turn-complete surface if one exists. Acceptance: tool-free and tool-using over-budget responses trigger the check, concise responses do not loop, subagent behavior is explicit, and savings refresh once per turn—or docs/parity clearly classify the feature as advisory.

- **CX19 — Replace synthetic Codex hook smoke coverage with semantic, versioned payload coverage** *(meta / reliability)* — `.claude/tests/unit/test_codex_event_contract.py:49-169` invents payloads and accepts any exit code in `{0, 2}` if there is no traceback; unexpected payloads can therefore no-op silently. Store sanitized fixtures for supported Codex versions covering reads, searches, Bash, apply_patch, Edit/Write, tool errors, available final-response events, and unknown MCP tools. Assert semantic outcomes, not non-crash. Acceptance: every supported matcher has a real-shape fixture and outcome assertion; unknown shapes fail open with bounded schema-only telemetry; schema drift creates a targeted failure or audit warning.

- **D1 — Add a troubleshooting section** *(documentation / recovery)* — Cover the common failures currently requiring source inspection: first-run model download failure, wrong venv path, empty or stale indexes, background refresh failures and `.claude/state/index-refresh.log`, and what an empty search result does to the search-first gate. Acceptance: each symptom has a check, likely cause, and recovery command.

- **P4 — Generate installer flag docs from argparse metadata** *(prose-to-code / doc drift)* — `DOCUMENTATION.md:37-51` hand-lists optional flags while `install.py:1930-1996` is authoritative. Render an `<!-- installer-flags -->` block from parser metadata or a shared registry. Acceptance: every public flag is documented unless explicitly hidden and CI catches drift.

- **A1 — Split shared subagent guidance from platform mechanics** *(architecture / divergent prose)* — Claude and Codex skills duplicate the output contract, prompt shape, noisy-verification pattern, and large-source digest guidance; only their agent/tool mechanics differ. Factor the shared contract into one generated source while keeping explicit platform-specific rules. Acceptance: return-shape and "do not paste" edits happen once and both installed skills retain their divergent mechanics.

- **P5 — Code the root-document canonical-home rules** *(meta / prose-to-code)* — The claudemd skill carries a hand-maintained topic-home table and asks agents to find duplicates manually. Move the mapping into structured config consumed by `claudemd_audit.py --docs` or a dedicated gate. Acceptance: the skill points to the gate and CI/release checks report non-canonical duplicate sections with file:line references.

- **D2 — Replace fragmented hook JSON with one merge-safe example** *(documentation / installability)* — `DOCUMENTATION.md:343-397` shows a base settings object followed by detached optional matcher fragments, leaving users to infer event placement and JSON merging. Generate or publish one valid, unified configuration and explain which file the installer owns. Acceptance: the example can be copied as valid JSON and includes the default hook set in correct event order.

- **D3 — Explain search-window and exclusion configuration** *(documentation / precision)* — The configuration table names `EXCLUDED_DIR_NAMES`, `EXCLUDED_DIR_PREFIXES`, and the 300-second search window but does not explain their behavioral differences or where to tune `WINDOW_SECONDS`. Acceptance: examples distinguish name-based from prefix-based exclusions and show how the gate window is configured.

- **D4 — Publish reproducible token-savings benchmarks** *(evidence / documentation)* — Measure the shipped strategies on a representative real codebase, including method, workload, baseline, variance, and agent/platform limits. Acceptance: another maintainer can rerun the benchmark and reproduce the report within stated tolerance; unverified savings claims are labeled as estimates.

- **CX20 — Codex compaction remains a nudge, not control parity** *(input / platform gap)* — Investigate whether the current Codex app exposes a compaction or session-rollover API. If available, invoke it and verify transcript size before recording measured savings. Otherwise keep the nudge, test hysteresis on live transcript paths, and record the limitation. Acceptance: either an oversized live session is compacted automatically with honest before/after telemetry, or docs/parity/telemetry consistently say Codex only receives an advisory nudge.

## Blocked / evidence collection

Do not implement these yet. Satisfy the unblock condition, then move the item into **Ready now** at the appropriate order.

| ID | Priority | Blocked on | Unblock signal |
|---|:---:|---|---|
| C1 | P1 | CX16 and a real Codex observation window | Genuine bash/grep near-misses show repeatable normalization candidates |

- **C1 — Widen cache keys for bash/grep and split TTLs** *(input / cache)* — Exact literal keys prevent semantically identical calls from hitting, but current Codex telemetry contains no genuine bash/grep observations because the dogfood install drifted stale. After CX16, collect a real data window; normalize only output-shape-neutral flags observed in near-misses, key grep on normalized `(pattern, path, glob, type)`, and expose `CONTEXT_CACHE_BASH_TTL` separately. `eb_telemetry_9jul26.md` §2 provides Claude-side examples but does not satisfy the Codex evidence requirement. Acceptance: the normalization allowlist is justified by captured cases, equivalent calls hit, meaning-changing calls miss, and bash/grep TTLs are independently configurable.

## Later

| ID | Priority | Why later |
|---|:---:|---|
| DX1 | P3 | Process improvement; no direct runtime saving |
| D5 | P3 | Marketing aid after core documentation is reliable |
| DX2 | P3 | Infrastructure cost only matters if perf variance becomes a problem |

- **DX1 — Add same-pattern propagation to the bugfix skill** *(process)* — After a bug fix, require a codebase-wide search for the root-cause construct and create backlog items for additional hits. Acceptance: `.claude/skills/bugfix/SKILL.md` contains the explicit search-and-record step.

- **D5 — Create an animated before/after demo** *(documentation / adoption)* — Show a full read versus targeted search after the troubleshooting and configuration documentation is stable.

- **DX2 — Consider a self-hosted runner for perf** *(infrastructure)* — The perf job downloads a roughly 130 MB embedding model and inherits hosted-runner CPU variance. Revisit only if cold-cache time or variance causes material delays or false failures; weigh that against runner maintenance and security.
