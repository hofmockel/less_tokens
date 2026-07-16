# Backlog

Planned work not yet started. Maintainer: add `CHANGELOG.md` entry + delete item here before merging. See [.claude/skills/bug-hunt/SKILL.md](.claude/skills/bug-hunt/SKILL.md) / [.claude/skills/bug-hunt/bughuntlog.md](.claude/skills/bug-hunt/bughuntlog.md) for the bug-hunt protocol.

Token-reduction strategy and rationale live in [DOCUMENTATION.md](DOCUMENTATION.md) → *Token-reduction strategy*. Shipped strategies use stable IDs (S8–S13). Rejected or resolved proposals move to [DECISIONS.md](DECISIONS.md) — don't re-propose without new evidence.

---

## Bugs

Confirmed defects found by code inspection. Each has a specific file and line reference.

| **Bug** | **Details** | **Status** |
|---|---|---|
| **Codex truncation install smoke is a false positive** | `install.py:1701-1715` invokes `truncate-output.py` with a small `"tool_output"` payload, but `agents/common/hooks/payload.py:73-78` only normalizes `tool_response` or `tool_result`. The adapter therefore sees an empty result and exits 0 without exercising truncation, so `install.py --check --agent codex` can report wrapper health while output parsing/replacement is broken. Fix the fixture to use a recognized output key and oversized content, then assert the cap/omission marker and expected hook result rather than mere process startup. Add a regression test that fails if the smoke payload is not actually truncated. | Open |
| **Codex parity audit accepts stale relative hook commands that fail outside the repo root** | `.claude/tools/codex_parity_audit.py:45-47` treats any command containing `.codex/hooks/<script>` as wired; it does not validate the absolute launcher/script paths emitted by current `install.py:806-831`. On 2026-07-16 the source repo's generated `.codex/hooks.json` still contained relative `.less_tokens/bin/python .codex/hooks/...` commands, yet the audit classified most strategies `best-effort-only` instead of detecting the already-fixed nested-cwd failure mode. Compare installed entries with `build_codex_hook_entries()` or at minimum require absolute launcher and script paths, and execute a representative command from a nested cwd. Acceptance: the stale file fails the audit; a current install passes. | Open |

---

## Token-Reduction Strategies

Primary mission: fewer tokens. Ordered by impact × enforceability. Each item names the bucket it attacks: **input** (context read in), **output** (prose/code Claude writes), **tool** (tool-result dumps), **fixed** (paid every turn regardless of task), **meta** (multiplies the others). The **fixed** bucket is the biggest blind spot — barely touched beyond the just-shipped claudemd skill.

### High Priority

- **Widen cache keys for bash/grep (normalize + split TTL)** *(input / cache)* — `cacheable_bash_command()`/`grep_key()` key on the exact literal command/pattern string, so semantically-identical repeats (e.g. the same `pytest` call ± `-v`) never hit. Near-miss instrumentation (additive-only) already shipped `f95a963`; zero cached-bash/grep events had fired on the Codex side of this repo specifically because its local `.codex/` install had drifted stale (fixed 2026-07-08 by re-running the installer), not because the allowlist was too narrow. A new audit on 2026-07-16 found the generated Codex layer stale again (relative hook commands, no `continue-freshness.py`, and missing filesystem PostToolUse wiring for `context-cache`), and `.less_tokens/state/near_misses.jsonl` still contained no genuine bash/grep observations, so this item remains evidence-blocked. First restore/verify the Codex dogfood install and collect a real data window. Then normalize keys by stripping a documented allowlist of output-shape-neutral flags (from observed near-misses, not a guess) before keying bash commands, hash `(pattern, path, glob, type)` post-normalization for grep, and expose `CONTEXT_CACHE_BASH_TTL` as its own config value (currently silently falls back to the grep TTL). Do not widen the allowlist blind. `eb_telemetry_9jul26.md` §2 has 13 real Claude-side grep near-miss examples from `ever_better` (incl. two same-pattern-reformatted pairs) — useful raw material for the normalization allowlist, but Claude-side, not the Codex-side data this item is actually waiting on.

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

The checked-in manifest/parity registry currently marks all 17 strategies shipped for Codex. Items below are delivery, enforcement, and live-contract gaps: adapter existence is not proof that Codex actually intercepted or replaced the intended content.

### High Priority

- **Prove and, if supported, implement real Codex tool-output replacement** *(tool / enforcement parity)* — `agents/codex/hooks/truncate-output.py:65-92` prints the shortened result and returns the shared hook code (currently 2 for truncation), but no live Codex test proves that this replaces the original tool result before the model receives it. `CHANGELOG.md:30` explicitly records that the Codex protocol was not verified when Claude moved to `hookSpecificOutput.updatedToolOutput`. Pickup: capture a real oversized Bash and filesystem-read PostToolUse payload, record exactly what stdout/stderr/exit status Codex consumes, and inspect the next model-visible context—not just terminal output. Add a live or harness-level regression that fails if the original oversized content remains visible. If Codex exposes an output-replacement JSON contract, implement it in the adapter and keep the existing measured-savings event only after successful replacement. If no such contract exists, document the platform blocker, stop labeling Codex truncation savings as measured, and downgrade the parity row rather than preserving a false guarantee. Acceptance: an oversized sentinel present only beyond the cap cannot be recovered from the next Codex turn, while the head/tail and omission marker remain available.

- **Codex final-response enforcement needs a real end-of-turn contract** *(output / enforcement parity)* — `hook_manifest.py:148-168` substitutes `PostToolUse .*` for Claude's `Stop|SubagentStop` on `terse-output` and `savings-html`; `agents/codex/hooks/terse-reminder.py:24-42` analyzes only a top-level `response` field. Unit tests manufacture that field (`test_codex_hooks.py:224-262`), but ordinary PostToolUse payloads may not contain the final assistant response, and a tool-free final turn fires no PostToolUse event at all. Pickup: capture live payloads for tool-using, tool-free, and subagent-final turns; determine whether Codex exposes a final-response/turn-complete event or another app callback; then wire terse checking and once-per-turn savings refresh to it. Keep PostToolUse only as an explicitly documented fallback. Acceptance: both tool-free and tool-using over-budget final responses trigger the check, concise responses do not loop, subagent behavior is stated/tested, and the savings page refreshes once after the final turn. If Codex exposes no end-of-turn surface, record a DECISIONS.md platform limitation and make the parity table say degraded/advisory rather than implying equivalent enforcement.

- **Make Codex dogfood installs self-diagnosing and recoverable from manifest drift** *(meta / install parity)* — on 2026-07-16 `codex_parity_audit.py --root .` found `continue-freshness` unwired, `context-cache` missing filesystem PostToolUse wiring, and `.codex/hooks.json`/its parent reported unwritable; inspection also found all installed commands still relative even though current `install.py:439-445,806-831` emits absolute Codex launcher/script paths. Because `.codex/` is generated/ignored and `install.py` refuses to target the source directory itself, the toolkit's own Codex dogfood install can silently lag the checked-in manifest. Provide a supported refresh path for this source repo (or a narrowly scoped generated-runtime refresh command), make audit/check compare every event+matcher+exact command and required script, and surface skipped/unwritable hook installation as a degraded result that cannot be mistaken for full enforcement. Acceptance: starting from the observed stale `.codex` state, one documented command produces all manifest entries with absolute paths; `codex_parity_audit.py` reports zero `unwired` rows; representative wrappers run from a nested cwd; a second refresh is a no-op.

### Medium Priority

- **Replace synthetic Codex hook-contract smoke coverage with semantic, versioned payload coverage** *(meta / reliability)* — `.claude/tests/unit/test_codex_event_contract.py:49-169` invents payloads for six tool names and accepts any exit code in `{0, 2}` so long as there is no traceback. `_codex_runtime.load_json_stdin()` (`agents/codex/hooks/_codex_runtime.py:36-45`) silently converts malformed/unexpected input to `{}`, and `map_read_or_search()` only recognizes exact `mcp__filesystem__read_file` plus names containing `search` (`:56-70`); broad `mcp__filesystem__.*` matchers can therefore fire while adapters no-op. Capture sanitized payload fixtures from supported Codex versions for reads, searches, Bash, apply_patch, Edit/Write, tool errors, final responses if available, and unknown MCP tools. For each manifest entry assert the semantic outcome (block/allow, mapped path/query, replacement/context output, state mutation), not merely non-crash. Add fail-open telemetry with event/tool/schema fingerprints—never content—so new shapes are visible without blocking users. Acceptance: every supported matcher has at least one real-shape fixture and outcome assertion; unknown shapes fail open but emit a bounded diagnostic; schema drift produces a targeted CI failure or audit warning.

- **Codex compaction remains a nudge, not control parity** *(input / platform gap)* — `agents/codex/hooks/compact-trigger.py:46-53` can detect a large transcript and ask for a fresh or compacted Codex session, but it cannot initiate compaction; tests intentionally assert that the message does not claim `/compact` support (`test_codex_hooks.py:269-337`). Investigate whether the current Codex app exposes a compaction/session-rollover API or supported action. If available, call it and verify the post-compaction transcript/summary size before logging measured savings. If unavailable, retain the nudge but classify it as advisory enforcement, test hysteresis and repeated-nudge behavior on live transcript paths, and record the platform blocker in DECISIONS.md. Acceptance: either an oversized live session is compacted automatically with honest before/after telemetry, or docs/parity/telemetry consistently state that Codex only receives a nudge and no automatic savings are claimed.

### Low Priority

---

## Developer Experience

### Low Priority

- **Bugfix skill: add same-pattern propagation step** *(process)* — After fixing any bug, require a codebase-wide search for the same pattern before closing. Add explicit checklist step to `.claude/skills/bugfix/SKILL.md`: grep for the root-cause construct (e.g. `endswith`, `offset`) across all `.py` files; open a backlog row for each additional hit. Prevents `endswith` and `offset=0` class of duplicates.

- **Consider GitHub self-hosted runners for the perf job** — the `perf` CI job downloads the fastembed model (~130 MB `BAAI/bge-small-en-v1.5`) and relies on `actions/cache`; a cold cache miss adds wall-clock time and network variance to timing results. A self-hosted runner with the model pre-installed in `~/.cache/huggingface` would remove both and give stable CPU baselines. Trade-off: infra maintenance + runner registration; only worth it if perf run times become a bottleneck or variance produces false failures. (Demoted: not on the token-reduction mission.)

---
