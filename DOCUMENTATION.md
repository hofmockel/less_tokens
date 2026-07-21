# Documentation

Full reference for installing, configuring, and using `less_tokens`.

---

## Prerequisites

- Python 3.9+
- A virtual environment for your project (`.venv`, `venv`, `env`, or `app/.venv`)
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) and/or Codex installed, depending on the selected agent target

---

## Installation

Clone less_tokens *into* the project you want to install it on. The installer targets the parent directory of the clone, so it works from any cwd:

```bash
# macOS / Linux
cd ~/myproject
git clone https://github.com/<you>/less_tokens.git
python3 less_tokens/install.py

# Windows
cd C:\myproject
git clone https://github.com/<you>/less_tokens.git
python less_tokens\install.py
```

Re-running after `git pull` performs a conservative install pass: existing files are skipped, hook wiring is deduplicated, and `search_config.py` only gains new variables. For an intentional safe upgrade of generated hooks and tools, use `--update` with the same `--agent` selection as the original install. `--update` preserves `search_config.py` and `index.db`.

> By default the installer builds the index after installation. Pass `--no-build` to defer the model download and index build until after configuring `search_config.py` (the Usage section covers the manual command).

The installer copies tools and schema into `.claude/tools/` and `.claude/schema/`, deploys hooks into `.claude/hooks/`, installs `fastembed` and `numpy`, and initializes `.claude/index.db`.

**Optional flags:**

| Flag | Effect |
|---|---|
| `--target PATH` | Install into PATH instead of the parent of the clone (testing / scratch projects) |
| `--yes` | Bypass the suspicious-target sanity check (fires when parent is `/` or `$HOME`) |
| `--force` | Shorthand for `--force-hooks --force-tools --force-config` |
| `--force-hooks` / `--force-tools` / `--force-config` | Overwrite the selected generated file class when it still matches a managed source |
| `--overwrite-modified` | Permit a selected `--force*` option to overwrite locally modified managed files |
| `--venv PATH` | Point to a venv not in a standard location |
| `--create-venv` | Create `.claude/.venv-tokens` when no venv is detected |
| `--skip-deps` | Skip `pip install` (dependencies already installed) |
| `--no-build` | Defer the default initial index build and model download |
| `--agent claude\|codex\|both` | Agent target: Claude Code (default), Codex, or both simultaneously |
| `--codex-savings balanced\|aggressive` | Select the Codex-only savings profile; `balanced` is the default |
| `--caveman` | Back-compatible; also copy `.claude/rules/` for terse output style |
| `--truncate` | Back-compatible; truncation hook is wired by default |
| `--compact` | Back-compatible; compaction trigger is wired by default |
| `--no-caveman` / `--no-truncate` / `--no-compact` | Opt out of default savings hooks |
| `--dry-run` | Preview the install without writing files |
| `--allow-merge` | Allow existing non-less_tokens files in managed tool/schema directories |
| `--local` | For Claude, write hook wiring to `.claude/settings.local.json` instead of project-shared settings |
| `--no-gitignore` | Do not add the managed ignore block for generated index/state artifacts |
| `--update` | Safely refresh generated hooks and tools without changing `search_config.py` or `index.db` |
| `--self-refresh` | Advanced dogfood mode: refresh this clone's own generated install; implies `--update` |
| `--check` | Verify an existing installation (see the Codex validation limitation below) |
| `--uninstall` | Remove a previous deployment |
| `--purge-index` | With `--uninstall`, also remove `index.db` and its WAL sidecars |

---

## Codex support

`--agent codex` (or `--agent both`) installs Codex adapter hooks under `.codex/hooks/` when that directory is writable. `.less_tokens/` is the shared product runtime: it holds the budget control-plane config, budget engine, telemetry state, report tools, and Codex command shims. The underlying index remains the shared project index at `.claude/index.db`, so Claude and Codex can search the same local corpus without maintaining two databases.

```bash
python3 less_tokens/install.py --agent codex
python3 less_tokens/install.py --agent both   # Claude + Codex simultaneously
```

Upgrade with the same agent selection used for installation:

```bash
cd ~/myproject/less_tokens
git pull
python3 install.py --update --agent codex   # or --agent both
```

Codex CLI requires matcher groups and command hooks to be nested. The installer owns the less_tokens entries in `.codex/hooks.json` and writes this shape (commands abbreviated here):

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "apply_patch|Edit|Write",
        "hooks": [
          {"type": "command", "command": "…/.less_tokens/bin/python …/.codex/hooks/index-refresh.py"}
        ]
      }
    ]
  }
}
```

Re-running `--update --agent codex` migrates the retired CX21 matcher-array form into this published event-keyed structure. Valid unrelated hook metadata is preserved. Malformed and pre-CX21 flat files fail before installation writes, because silently rebuilding an unknown contract could discard user hooks. Detected Codex executables must fall within the live-verified `0.142.3–0.144.6` support window.

Contract sources: [current Codex hooks reference](https://learn.chatgpt.com/docs/hooks), [release-tagged `0.142.3` schemas](https://github.com/openai/codex/tree/rust-v0.142.3/codex-rs/hooks/schema/generated), and [release-tagged `0.144.5` schemas](https://github.com/openai/codex/tree/rust-v0.144.5/codex-rs/hooks/schema/generated). The hooks reference warns that `main` schemas can include unreleased fields, so version-tagged schemas and live probes are the compatibility evidence.

**What gets installed:**

| Path | Purpose |
|---|---|
| `.less_tokens/config/budget.json` | Shared budget-control config for Claude and Codex |
| `.less_tokens/hooks/budget/` | Shared budget engine used by both agent adapters |
| `.less_tokens/tools/` | Codex command shims that run the single `.claude/tools/` implementation |
| `.less_tokens/tools/budget_report.py` | v2 budget telemetry report |
| `.less_tokens/tools/budget_doctor.py` | config and recent-pressure diagnosis |
| `.less_tokens/bin/python` | Venv-backed Python launcher for Codex commands |
| `.less_tokens/schema/` | SQLite schema |
| `.less_tokens/hooks/` | Shared hook support imported by Codex adapters |
| `.less_tokens/state/` | Shared budget telemetry plus Codex runtime state |
| `.codex/hooks/` | Codex adapter hooks (wired to `.codex/hooks.json` when writable) |
| `AGENTS.md` | Token-discipline fragment appended via HTML comment sentinels |
| `.less_tokens/skills/less-tokens/` | Fallback skill path when `.codex/` is not writable |
| `.claude/index.db` | Shared vector index used by both agents |

**Compatibility:**

<!-- hook-parity: begin -->

Feature parity means the same strategy is shipped for both agents. Enforcement parity is intentionally different: Claude hooks are direct enforcement, while Codex hooks are best-effort adapters through `.codex/hooks.json`.

| Strategy | Feature parity | Claude enforcement | Codex enforcement |
|---|---|---|---|
| `budget-observer` | yes | enforced; `.claude/hooks/budget-observer.py`; PreToolUse `Read|Grep|Glob|Bash`, PostToolUse `Read|Grep|Glob|Bash|Edit|Write` | best-effort; `.codex/hooks/budget-observer.py`; PreToolUse `mcp__filesystem__.*|Bash`, PostToolUse `Bash|mcp__filesystem__.*|apply_patch|Edit|Write` |
| `search-first` | yes | enforced; `.claude/hooks/search-first.py`; PreToolUse `Read`, PreToolUse `Grep` | best-effort; `.codex/hooks/search-first.py`; PreToolUse `mcp__filesystem__.*|Bash` |
| `read-guard` | yes | enforced; `.claude/hooks/read-guard.py`; PreToolUse `Read` | best-effort; `.codex/hooks/read-guard.py`; PreToolUse `mcp__filesystem__.*|Bash` |
| `auto-slice` | yes | enforced; `.claude/hooks/auto-slice.py`; PreToolUse `Read` | best-effort; `.codex/hooks/auto-slice.py`; PreToolUse `mcp__filesystem__.*|Bash` |
| `grep-first-read` | yes | enforced; `.claude/hooks/grep-first-read.py`; PreToolUse `Read` | best-effort; `.codex/hooks/grep-first-read.py`; PreToolUse `mcp__filesystem__.*|Bash` |
| `read-after-edit` | yes | enforced; `.claude/hooks/read-after-edit.py`; PreToolUse `Read` | best-effort; `.codex/hooks/read-after-edit.py`; PreToolUse `mcp__filesystem__.*|Bash` |
| `continue-freshness` | yes | enforced; `.claude/hooks/continue-freshness.py`; PreToolUse `Read` | best-effort; `.codex/hooks/continue-freshness.py`; PreToolUse `mcp__filesystem__.*|Bash` |
| `context-cache` | yes | enforced; `.claude/hooks/context-cache.py`; PreToolUse `Read|Grep`, PostToolUse `Read|Grep` | best-effort; `.codex/hooks/context-cache.py`; PreToolUse `mcp__filesystem__.*|Bash`, PostToolUse `Bash`, PostToolUse `mcp__filesystem__.*` |
| `post-edit-diff` | yes | enforced; `.claude/hooks/post-edit-diff.py`; PostToolUse `Edit|Write` | best-effort; `.codex/hooks/post-edit-diff.py`; PostToolUse `apply_patch|Edit|Write` |
| `index-refresh` | yes | enforced; `.claude/hooks/index-refresh.py`; PostToolUse `Edit|Write` | best-effort; `.codex/hooks/index-refresh.py`; PostToolUse `apply_patch|Edit|Write` |
| `agent-md-budget` | yes | enforced; `.claude/hooks/claudemd-budget.py`; PostToolUse `Edit|Write` | best-effort; `.codex/hooks/agentsmd-budget.py`; PostToolUse `Edit|Write` |
| `lean-output` | yes | enforced; `.claude/hooks/lean-output.py`; PostToolUse `Bash` | best-effort; `.codex/hooks/lean-output.py`; PostToolUse `Bash` |
| `listing-guard` | yes | enforced; `.claude/hooks/listing-guard.py`; PreToolUse `Bash` | best-effort; `.codex/hooks/listing-guard.py`; PreToolUse `Bash` |
| `truncate-output` | Claude only; default-on optional | enforced; `.claude/hooks/truncate-output.py`; PostToolUse `Bash|Read|WebFetch|Glob` | missing |
| `subagent-cap` | Claude only; default-on optional | enforced; `.claude/hooks/subagent-cap.py`; PostToolUse `Task` | missing |
| `subagent-fanout` | Claude only | enforced; `.claude/hooks/subagent-fanout.py`; PreToolUse `Task`, PostToolUse `Task` | missing |
| `compact-trigger` | yes; default-on optional | enforced; `.claude/hooks/compact-trigger.py`; PostToolUse `.*` | best-effort; `.codex/hooks/compact-trigger.py`; PreCompact `manual|auto`, PostCompact `manual|auto` |
| `subagent-guidance` | Codex only | missing | best-effort; `.codex/hooks/subagent-guidance.py`; SubagentStart `*` |
| `terse-output` | yes; default-on optional | enforced; `.claude/hooks/caveman-reminder.py`; Stop `*`, SubagentStop `*` | best-effort; `.codex/hooks/terse-reminder.py`; Stop `*`, SubagentStop `*` |
| `savings-html` | yes | enforced; `.claude/hooks/savings-html.py`; Stop `*`, SubagentStop `*` | best-effort; `.codex/hooks/savings-html.py`; Stop `*`, SubagentStop `*` |

<!-- hook-parity: end -->

This is feature parity, not identical enforcement parity. The shared source of truth is `agents/common/hooks/hook_manifest.py`; `agents/common/hooks/parity.json` records whether each strategy is shipped for Claude and Codex. Claude hooks are enforced directly by Claude Code. Codex hooks are adapter-based and best-effort through `.codex/hooks.json`, so they can lose enforcement if `.codex/` is not writable or Codex changes event payloads/matchers.

**Parity is the floor, not the ceiling.** Every shipped strategy should reach both agents; regressions below that bar are bugs. Claude also has reliable controls that Codex does not expose, including direct PreToolUse/Stop hooks, per-agent `agent_overrides.claude`, and model-aware thresholds. When those Claude-only controls reduce tokens without changing Codex behavior, they are valid improvements rather than parity violations. The isolation boundaries are `agent_overrides.claude` for budget settings and `.claude/settings.json` for Claude-only hook wiring.

**Why Claude is easier to enforce:**

Claude Code exposes stable hook events for the token-heavy operations less_tokens wants to shape: `Read`, `Grep`, `Glob`, `Bash`, `Edit`, `Write`, and `Stop`. Those events carry purpose-specific payloads such as `file_path`, `offset`, `limit`, command text, tool output, and transcript path. That lets a hook block a whole-file read before it happens, replace it with an exact slice, compact oversized Bash output after it returns, or inspect the final assistant message through the `Stop` event. The install target is also straightforward: `.claude/hooks/` plus `.claude/settings.json` or `.claude/settings.local.json`.

Codex has the same strategy coverage, but it needs a translation layer. Filesystem activity often arrives through MCP-style tool names such as `mcp__filesystem__.*`, edits can arrive as `apply_patch` instead of a single file-oriented `Edit|Write`, and output-style enforcement does not have Claude's exact `Stop` hook shape. The `.codex/hooks.json` file may also be absent or unwritable in some installs. For that reason, Codex support installs thin adapters in `.codex/hooks/`, shared logic in `.less_tokens/hooks/`, command shims in `.less_tokens/tools/`, and state under `.less_tokens/state/`. Those adapters normalize Codex payloads into the shared hook checks where possible, and fail open when the Codex event shape cannot be trusted.

Codex subagents are a Codex app tool surface, not an installed `less_tokens` feature. Use them only when the user explicitly asks for delegation or parallelism. `.codex/hooks.json` cannot intercept broad parent reasoning and move it into a child automatically; `less_tokens` can only provide small prompt templates, installed search/read tools, hook wrappers, and smoke checks for those wrappers. The Codex `less-tokens` skill documents the prompt shape: prefer `fork_context=false`, pass pointers/search commands instead of payloads, use `explorer` for read-only questions, reserve `worker` for disjoint file ownership, and require compact returns.

**Known limitations:**

- Codex hook enforcement is best-effort — interception depends on `.codex/hooks.json` being writable and Codex emitting the expected tool events. If `.codex/` is not writable at install time, the skill and `AGENTS.md` fragment are installed but hooks are skipped.
- `.codex/hooks.json` write is optional — install always exits 0 regardless of hook wiring success.
- CX26 writes the published event-keyed contract and keeps the retired CX21 matcher-array shape as upgrade/uninstall input only. Live headless tests proved `PreToolUse:Bash` blocking and `PreToolUse:apply_patch` delivery on `codex-cli 0.142.3` and the ChatGPT desktop-bundled `0.144.5`; release-labeled sanitized fixtures live under `.claude/tests/fixtures/codex-hooks/`.
- The verified surface is headless `codex exec`. Interactive CLI, desktop UI/app-server, IDE, hosted, and specialized tool paths are not inferred from those runs. Current official docs say hosted tools and some specialized paths can bypass local tool hooks.
- CX28 verified that Codex 0.144.6 `PostToolUse` can add feedback but cannot replace or suppress the original tool result: `suppressOutput` is explicitly unsupported and there is no `updatedToolOutput` equivalent. Codex output truncation is therefore unwired and records no savings; CX27 pre-execution deny/rewrite controls remain the supported fallback. CX29 replaces the former wildcard `PostToolUse` approximations with native `Stop`, `SubagentStart`, `SubagentStop`, `PreCompact`, and `PostCompact` wiring on the verified 0.144.6 contract. Older releases keep an explicit best-effort label because lifecycle delivery was not proven there. Historical CX17/CX18/CX23 findings describe the retired matcher-array representation and must not be treated as current-contract proof.
- `install.py --check --agent codex` verifies the release window, event-keyed file shape, manifest coverage, and canonical `[features].hooks` state. Hook trust is definition-hash scoped and has no stable non-interactive query, so the check directs users to `/hooks` and does not claim live enforcement from configuration alone.
- Budget telemetry lives in `.less_tokens/state/events.jsonl` for both agents. Codex runtime state also lives in `.less_tokens/state/`; older Claude search state remains in `.claude/state/`. The vector index is shared at `.claude/index.db`.
- Terse output style (`--caveman`) wires Claude's Stop hook and Codex's concise-reminder hook; Codex enforcement remains best-effort like the other Codex hooks.
- Codex has extra adapter handling for `apply_patch`; Claude does not need that path because Claude edits arrive through `Edit|Write`.

See `agents/common/hooks/hook_manifest.py` for the exact hook matrix, release window, parser, and renderer, and `agents/common/hooks/parity.json` for the CI-checked shipped/missing parity data. Audit a Codex install's actual `.codex/hooks.json` wiring against that manifest with:

```bash
.less_tokens/bin/python .less_tokens/tools/codex_parity_audit.py
```

For repeatable savings checks, run:

```bash
.claude/bin/python .claude/tools/eval_sessions.py --report .claude/state/session-eval.md
```

The harness is deterministic and fixture-based; it is useful for trend tracking, not a substitute for live Claude/Codex usage data.

---

## Subagent support

Subagents can reduce parent-context noise when they absorb independent exploration or noisy verification, but every spawn also pays fixed instructions/tool-schema cost. `less_tokens` therefore treats delegation as an explicit, platform-specific tool: it does not spawn children automatically, and the installed guidance says to skip delegation for a single search, small read, or short test command.

### Shipped behavior

| Capability | Claude | Codex |
|---|---|---|
| Return-size control (SA1) | `PostToolUse:Task` runs `.claude/hooks/subagent-cap.py`; returns over `MAX_SUBAGENT_OUTPUT_CHARS` (default 6,000) keep verdict/recommendation/summary/blocker-style fields when possible, otherwise use bounded head/tail elision. The hook replaces the parent-visible tool result and logs measured elided characters as `subagent-cap`. | No hookable subagent-return boundary is available, so no automatic cap is claimed. |
| Fan-out measurement (SA2) | `PreToolUse:Task` records serialized prompt size and `PostToolUse:Task` pairs it with return size, subagent type, and session metadata in one `subagent_fanout` event. Measurement is always wired and never mutates output. | No equivalent `Task` boundary; no fan-out event is emitted. |
| Delegation guidance | Installed Claude skill recommends narrow `explorer` and `verifier` agents, pointer-only context, disjoint ownership, and compact returns. | Installed Codex skill requires explicit user authorization, defaults to `fork_context=false`, distinguishes `explorer` from `worker`, and requires compact four-field returns. |
| Subagent completion | Claude `terse-output` and `savings-html` also wire `SubagentStop`. | Best-effort tool hooks do not provide equivalent end-of-subagent enforcement. |

SA1 follows the default truncation profile: `--no-truncate` disables both generic output truncation and `subagent-cap`. SA2 remains active because it only records cost. Both are Claude-only in `agents/common/hooks/parity.json`; this is a real platform boundary, not missing documentation or an implied parity promise.

### Delegation contract

Use a child only when its discarded exploration/log output is likely to exceed its startup cost. Give it an objective, `path:line` pointers or a semantic-search command, the minimum allowed reads, and a compact return contract. Parallel children should own independent tasks or disjoint files; the parent should continue only non-overlapping work.

Required return fields:

```text
files changed: <paths or none>
findings: <file:line findings only>
verification: <commands or checks run>
blockers: <none or concrete blocker>
```

Do not paste full files, raw logs, or complete diffs into either the spawn prompt or the return. On Codex, prefer `fork_context=false` unless the child genuinely needs conversation history. On Claude, prefer the installed narrow agent definitions over `general-purpose` when their tool allowlists fit.

### Telemetry

Claude writes both SA1 savings and SA2 cost measurements to `.claude/state/savings.jsonl`. A paired SA2 record has this shape:

```json
{
  "event": "subagent_fanout",
  "subagent_type": "explorer",
  "prompt_chars": 1200,
  "return_chars": 3400,
  "session_id": "…",
  "session_source": "…"
}
```

`subagent_fanout` is an `event`, not a savings `strategy`: prompt/return sizes are costs and are deliberately excluded from measured and upper-bound savings totals. An unmatched post-install completion still records `prompt_chars: 0` rather than dropping the observed spawn. Inspect session or all-time results with:

```bash
.claude/bin/python .claude/tools/stats.py
.claude/bin/python .claude/tools/stats.py --all
```

### Roadmap and evidence gates

The roadmap is derived from [BACKLOG.md](BACKLOG.md), which remains canonical for state and acceptance criteria.

| ID | State | Candidate | Gate before implementation |
|---|---|---|---|
| SA1 | Shipped | Cap oversized child returns with a generic key-field/head-tail digest. | Already measured through `subagent-cap` savings records. |
| SA2 | Shipped / collecting evidence | Pair prompt and return size for every observed Claude `Task` spawn. | Collect a representative dogfood window before interpreting downstream opportunities. |
| SA3 | Blocked on SA2 | Replace full-file spawn context with pointers and child-side guarded reads. | SA2 must show prompt-side size is a material share of fan-out cost; implementation must shrink prompts without reducing task success. |
| SA4 | Blocked on SA2 + payload capture | Scope budget state per subagent to prevent last-write-wins contention. | A live `Task` payload must expose a child session ID distinct from the parent, and concurrent children must demonstrate meaningful contention risk. Otherwise record the platform limit and park it. |
| SA5 | Blocked on SA2 | Apply role-specific digests, such as QA failure lines or architecture recommendations. | At least two subagent types must show a measurable advantage over SA1's generic cap; rules must live in versioned configuration. Otherwise keep the generic cap. |
| SA6 | Later / speculative | Digest and discard replayed full child transcripts at `SubagentStop`. | Reopen only if a future harness actually replays child transcripts to the parent; current Claude behavior does not. |

A1 is the documentation-maintenance workstream alongside this runtime roadmap: generate the shared delegation contract once while retaining separate Claude/Codex mechanics. It does not change spawn behavior.

---

## Configuration

Search and indexing are configured in `.claude/tools/search_config.py`. Budget behavior is configured separately in `.less_tokens/config/budget.json`. Codex commands under `.less_tokens/tools/` are compatibility shims that import and run the same `.claude/tools/` search code, so `.less_tokens/tools/search_config.py` is not a separate source of truth.

The installer prints the exact line to paste in. At minimum, set your venv path and the source directories to index:

```python
# .claude/tools/search_config.py

VENV_PY = _venv_python(".venv")               # change to your venv location
INDEXED_SOURCE_DIRS = ("src/", "schema/")      # dirs whose .py and .sql files get indexed
```

All variables:

| Variable | Purpose |
|---|---|
| `VENV_PY` | Venv python path (handles Win/macOS/Linux automatically) |
| `INDEXED_SOURCE_DIRS` | Subdirs to index for `.py` and `.sql` files |
| `INDEXED_ROOT_GLOBS` | Root-level patterns to index (default: `*.md`) |
| `EXCLUDED_DIR_NAMES` | Directory names to skip (e.g. `node_modules`) |
| `EXCLUDED_DIR_PREFIXES` | Path prefixes to skip (e.g. `legacy/`) |
| `SOURCE_TYPES` | Labels for `--source-type` CLI filtering |
| `MAX_TOOL_OUTPUT_CHARS` | Truncation ceiling for Bash/Read/WebFetch results (set 0 to disable) |
| `TOOL_OUTPUT_HEAD_LINES` | Bash head lines kept on truncation |
| `TOOL_OUTPUT_TAIL_LINES` | Bash tail lines kept on truncation (errors live here) |
| `CODEX_MAX_TOOL_OUTPUT_CHARS` / `CODEX_MAX_FILESYSTEM_READ_CHARS` | Tighter Codex-only truncation ceilings; env overrides are `LESS_TOKENS_CODEX_MAX_TOOL_OUTPUT_CHARS` and `LESS_TOKENS_CODEX_MAX_FILESYSTEM_READ_CHARS` |
| `MAX_SESSION_CHARS` | Session transcript size that triggers a `/compact` reminder (set 0 to disable) |
| `AGENT_MODEL` | Optional Claude model ID used for default search `k` and Claude-only threshold scaling |
| `STATE_DIR` | Where the search-first state file lives (default `.claude/state/`) |

`INDEXED_SOURCE_DIRS` also feeds JS/TS indexing for `.js`, `.jsx`, `.ts`, and `.tsx` files.

### Budget control plane

The budget control plane scores proposed context before it enters the agent transcript. It can replace broad reads with targeted slices, summarize oversized tool output, defer low-value context, block repeated reads/searches, and trigger pressure-based compaction snapshots.

Configure it in `.less_tokens/config/budget.json`:

| Mode | Behavior |
|---|---|
| `observe` | Record v2 telemetry only; never changes hook behavior |
| `advise` | Record telemetry and print concise suggestions |
| `enforce` | Block actionable waste when a replacement or bypass path exists |
| `strict` | Enforce plus block oversized unscored context |

The default mode is `observe`. Events are appended to `.less_tokens/state/events.jsonl`; compact per-agent session snapshots are written beside it, such as `.less_tokens/state/claude-session.json` and `.less_tokens/state/codex-session.json`.

Pre-tool decision events include `invocation_id`, `event_id`, `input_characters`, and
`estimated_input_tokens`. Native call identifiers such as `tool_use_id` are preferred; a stable
fingerprint of the session, phase, tool, and canonical input is used when the surface omits one.
Input size is recorded once per agent/session/invocation/phase even when one call produces several
candidate decisions or the hook payload is retried; later events keep the correlation IDs and
record zero input size so reports cannot double-count the same model-visible input.

`agent_overrides` lets one agent use tighter limits without changing the shared defaults or the other agent's effective budget. The shipped project config uses `agent_overrides.claude` for lower Claude limits on retrieved context, tool output, full-file reads, single tool outputs, and broad directory listings. Codex keeps its own effective profile through `agent_overrides.codex` and the built-in defaults in `agents/common/budget/config.py`.

Example shape:

```json
{
  "agent_overrides": {
    "claude": {
      "categories": {
        "retrieved_context": 6000,
        "tool_output": 2000
      },
      "hard_caps": {
        "full_file_read": 2000,
        "single_tool_output": 1500,
        "directory_listing": 600
      }
    },
    "codex": {}
  }
}
```

Inspect budget behavior with:

```bash
.claude/bin/python .less_tokens/tools/budget_report.py
.claude/bin/python .less_tokens/tools/budget_doctor.py
```

For Codex-only installs, the same tools can be run through the Codex launcher:

```bash
.less_tokens/bin/python .less_tokens/tools/budget_report.py
.less_tokens/bin/python .less_tokens/tools/budget_doctor.py
```

Use the escape hatch only when the agent truly needs the broad context: set `less_tokens_bypass: true`, set `tool_input.less_tokens_bypass: true`, or include `less_tokens: allow` / `less_tokens: bypass` in string input.

---

## Usage

### Build the index

Run this once after configuring, and again whenever you want a full refresh:

```bash
.claude/bin/python .claude/tools/embeddings.py refresh
```

For Codex-only workflows, `.less_tokens/bin/python .less_tokens/tools/embeddings.py refresh` remains supported as a shimmed command path.

> First run downloads the embedding model (~130 MB to `~/.cache/huggingface`). Subsequent runs are incremental and typically take under a second.

### Search

```bash
.claude/bin/python .claude/tools/search.py "your query"
```

For Codex-only workflows, `.less_tokens/bin/python .less_tokens/tools/search.py` remains supported as a shimmed command path.

**Examples:**

```bash
.claude/bin/python .claude/tools/search.py "how are imports validated"
.claude/bin/python .claude/tools/search.py "cash floor logic" --source-type code
.claude/bin/python .claude/tools/search.py "deployment steps" -k 5 --json
```

### Verify the index

```bash
.claude/bin/python .claude/tools/embeddings.py health   # exits 1 if any source has no chunks
.claude/bin/python .claude/tools/db.py verify           # prints row counts per source type
```

### Token savings tracking

Track how many chars and tokens each strategy saves across a session.

Tracking is **always on and local-only** from the first session of every install — there is no enable flag. Each event appends one JSON record to the active state directory (`.claude/state/savings.jsonl` for Claude, `.less_tokens/state/savings.jsonl` for Codex); the log is never transmitted. Records store exact characters (`kept_chars`/`elided_chars`) plus `basis`, `content_kind`, `where`, and `session_id`; tokens are derived at report time, not stored.

Disable local logging with the `LESS_TOKENS_NO_STATS=1` environment variable.

**Commands:**

```bash
.claude/bin/python .claude/tools/stats.py              # show session table (last 8h)
.claude/bin/python .claude/tools/stats.py --all        # show all-time totals
.claude/bin/python .claude/tools/stats.py --report     # write .claude/state/savings-report.md and print table
.claude/bin/python .claude/tools/stats.py --html       # write .claude/state/savings.html
```

Also accessible as:

```bash
.claude/bin/python .claude/tools/embeddings.py savings
.less_tokens/bin/python .less_tokens/tools/stats.py --html  # Codex shim; writes .less_tokens/state/savings.html
```

**Example output:**

```
## Session (last 8h · 8 events)

| Strategy               | Events |  Chars saved |  ~Tokens saved |
|------------------------|--------|--------------|----------------|
| Truncation             |      3 |       18,100 |          4,525 |
| Search-first block     |      2 |       22,600 |          5,650 |
| Search (vs full file)  |      2 |       20,300 |          5,075 |
| Compaction nudges      |      1 |            — |              — |
|------------------------|--------|--------------|----------------|
| **Total**              |        | **61,000**   |     **15,250** |
```

Token estimates use 4 chars ≈ 1 token. Search savings compare chunk text returned against the full size of matched files on disk.

### Terse output mode

Append the terse-output rule to your `CLAUDE.md`:

```bash
cat .claude/rules/caveman.md >> CLAUDE.md
```

Full spec, including banned filler phrases and before/after examples: [.claude/rules/caveman.md](.claude/rules/caveman.md). The installer flag is still named `--caveman` for backward compatibility.

---

## Wiring into Claude Code

### 1. Add to CLAUDE.md

```markdown
## Search Before Read — MANDATORY

Before reading any indexed file in full, run vector search first:

    .claude/bin/python .claude/tools/search.py "QUERY"

Indexed sources: [list your dirs here]

Use `Read` directly only when search returns no relevant chunks,
when you need to edit a file, or when the index is unavailable.
```

### 2. Add hooks to `.claude/settings.local.json`

The installer writes `.claude/bin/python` as a venv-backed launcher, so hook commands do not depend on system Python packages.

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Read",
        "hooks": [{"type": "command", "command": ".claude/bin/python .claude/hooks/search-first.py"}]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [{"type": "command", "command": ".claude/bin/python .claude/hooks/index-refresh.py"}]
      }
    ]
  }
}
```

**Optional — terse-output nudge hook** (fires if Claude uses verbose filler):

```json
{
  "matcher": ".*",
  "hooks": [{"type": "command", "command": ".claude/bin/python .claude/hooks/caveman-reminder.py"}]  // Stop event
}
```

**Optional — tool output truncation hook** (caps oversized Bash/Read/WebFetch results). Add as another `PostToolUse` entry, **before** the terse-output entry if both are present:

```json
{
  "matcher": "Bash|Read|WebFetch",
  "hooks": [{"type": "command", "command": ".claude/bin/python .claude/hooks/truncate-output.py"}]
}
```

Tune the base ceiling in `.claude/tools/search_config.py` via `MAX_TOOL_OUTPUT_CHARS` (default `4000`; set `0` to disable). If `AGENT_MODEL` is set to a known Claude model in `model_profiles.py`, Claude scales this ceiling at hook import time: Haiku is tighter, standard Sonnet keeps the configured default, and Opus or 1M Sonnet get more room. Codex adapters do not use `AGENT_MODEL`; they use separate defaults from `CODEX_MAX_TOOL_OUTPUT_CHARS` and `CODEX_MAX_FILESYSTEM_READ_CHARS`, with matching `LESS_TOKENS_CODEX_*` environment overrides.

**Optional — conversation compaction trigger** (nudges `/compact` when session transcript grows large):

```json
{
  "matcher": ".*",
  "hooks": [{"type": "command", "command": ".claude/bin/python .claude/hooks/compact-trigger.py"}]
}
```

Tune the base threshold in `.claude/tools/search_config.py` via `MAX_SESSION_CHARS` (default `500_000` ≈ 125k tokens; set `0` to disable). Claude scales this value with `AGENT_MODEL` when the model is known, using the same model-profile scale as truncation. The hook also has built-in hysteresis: once tripped, it only re-fires after the transcript grows by another 25%.

### 3. Optional: session-start preflight

```bash
.claude/bin/python .claude/tools/embeddings.py refresh   # incremental, ~1s when nothing changed
.claude/bin/python .claude/tools/embeddings.py health    # fail fast if index is stale
```

---

## Repository layout

All source lives under `.claude/` — the same structure that gets deployed into host projects.

**Source repo** (`less_tokens/`):
```
less_tokens/
├── install.py                 # cross-platform installer
└── .claude/
    ├── hooks/                 # deployed to <host>/.claude/hooks/
    │   ├── search-first.py        # PreToolUse: gate Read on indexed files
    │   ├── index-refresh.py       # PostToolUse: re-embed after Edit/Write
    │   ├── caveman-reminder.py    # Stop: nudge back to terse output
    │   ├── truncate-output.py     # PostToolUse: cap oversized Bash/Read/WebFetch results
    │   └── compact-trigger.py     # PostToolUse: nudge /compact when transcript grows large
    ├── rules/                 # deployed to <host>/.claude/rules/
    │   └── caveman.md             # CLAUDE.md snippet for terse output style
    ├── schema/                # deployed to <host>/.claude/schema/
    │   └── index.sql              # documents table schema
    ├── skills/                # Claude Code skills (not deployed; dev tooling only)
    │   └── bug-hunt/
    │       └── SKILL.md           # bug-hunt protocol and round log
    ├── tests/                 # test suite (not deployed)
    │   ├── unit/
    │   └── integration/
    └── tools/                 # deployed to <host>/.claude/tools/
        ├── search_config.py       # ← only file to edit after install
        ├── embeddings.py          # build/refresh the vector index
        ├── search.py              # semantic search CLI
        ├── db.py                  # SQLite helpers
        ├── savings_log.py         # per-event savings logger (used by hooks)
        └── stats.py               # savings tracker CLI (report; always on)
```

**Deployed layout** (inside the host project's `.claude/`):
```
<host-project>/
├── .claude/
│   ├── .venv-tokens/          # isolated Python env for fastembed/numpy
│   ├── bin/python             # venv-backed launcher for Claude commands
│   ├── hooks/                 # hook scripts (wired in settings.json)
│   ├── index.db               # SQLite vector index (regenerable)
│   ├── rules/                 # terse output rule file (if --caveman was passed)
│   ├── schema/                # index.sql schema
│   ├── state/                 # runtime state (last-search, logs)
│   └── tools/                 # search_config.py, embeddings.py, search.py, …
├── .less_tokens/              # shared budget control plane + Codex runtime
│   ├── bin/python             # venv-backed launcher for Codex commands
│   ├── config/budget.json     # observe/advise/enforce/strict budget config
│   ├── hooks/budget/          # shared budget engine
│   ├── hooks/                 # shared hook support for Codex adapters
│   ├── schema/
│   ├── state/                 # events.jsonl and per-agent session state
│   └── tools/                 # budget tools plus compatibility shims
├── .codex/hooks/              # Codex adapters when .codex is writable
├── AGENTS.md                  # Codex token-discipline block
└── less_tokens/               # the clone; not touched after install
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full workflow. In short: fork, add a [BACKLOG.md](BACKLOG.md) entry, open a PR. Check [DECISIONS.md](DECISIONS.md) first — a proposal already rejected there needs new evidence, not a repeat pitch.

---

## License

MIT — see [LICENSE](LICENSE).

---

## `.claudeignore`

Claude Code respects a `.claudeignore` file (same syntax as `.gitignore`) to exclude files from its project file scope — files listed there won't be surfaced as context candidates or suggested for reading.

`less_tokens` ships a `.claudeignore` that excludes files Claude doesn't need when doing code work in this repo:

| Entry | Reason |
|---|---|
| `README.md` | User-facing marketing page; content is in `DOCUMENTATION.md` |
| `DOCUMENTATION.md` | Reference docs; Claude reads source, not its own docs |
| `CHANGELOG.md` | History log; not relevant to active development |
| `.github/` | CI workflow config; rarely needs reading during development |

**When installing into your own project**, add a `.claudeignore` at the project root to exclude any large files Claude doesn't need for its day-to-day work — test fixtures, generated output, vendored assets, docs:

```
# .claudeignore example
docs/
tests/fixtures/large_dataset/
dist/
*.lock
```

The fewer files in scope, the less noise in tool suggestions and directory listings.

---

## Documentation backlog

Documentation gaps are prioritized with all other work in [BACKLOG.md](BACKLOG.md). Keeping one queue prevents resolved gaps from lingering here and makes dependencies on code work visible.

---

## Architecture internals

_Moved from CLAUDE.md to keep that file lean. Indexed — reachable by search._

The source tree has a Claude runtime, a Codex adapter layer, and shared hook logic:

```
.claude/
  hooks/           ← PreToolUse / PostToolUse / Stop hooks
  rules/           ← Output style rules
  skills/          ← Claude Code skills (bug-hunt, claudemd)
  tools/           ← Core Python scripts deployed to host projects
  schema/          ← SQL schema deployed to host projects
  tests/           ← Unit and integration test suites
  commands/        ← /build-index, /search, /def slash commands
agents/
  common/hooks/    ← agent-neutral hook checks used by adapters
  common/skills/   ← shared skill templates plus platform overlays
  claude/skills/   ← Claude skills generated or installed per project
  codex/hooks/     ← thin Codex hook adapters
  codex/skills/    ← Codex skills
```

### Layer split

**Agent-agnostic core (`.claude/tools/` and `.claude/schema/`)**
- `.claude/tools/search_config.py` — the single config file users edit; all runtime constants live here including `VENV_PY`, `INDEXED_SOURCE_DIRS`, `STATE_DIR`, truncation limits, compaction threshold, and optional `AGENT_MODEL`
- `.claude/tools/model_profiles.py` — Claude model metadata used for default search `k` and Claude-only threshold scaling
- `.claude/tools/embeddings.py` — chunks source files by structure (Python AST, markdown headings, SQL statements, JS/TS declarations), embeds with `BAAI/bge-small-en-v1.5` via `fastembed`, upserts into `.claude/index.db` with content-hash diffing
- `.claude/tools/search.py` — cosine similarity search over stored float32 vectors; writes `STATE_DIR/last-search` on every run so the search-first gate knows a search occurred
- `.claude/tools/db.py` — SQLite helpers; `connect_index()` opens `.claude/index.db`
- `.claude/tools/symbols.py` — exact symbol index for Python and JS/TS; `symbols.py <name>` (and the `/def` command) returns a definition's exact `file:line` + a `Read(offset,limit)`, no grep dump. Self-creating `symbols` table; refreshes when sources change
- `.less_tokens/tools/*.py` — generated Codex compatibility shims; these keep existing Codex command paths working while `.claude/tools/` remains the single implementation and config source.
- `.claude/schema/index.sql` — `documents` table with `(source_path, source_key)` unique constraint; `embedding_model` column exists per row for planned multi-model support

**Budget control plane (`.less_tokens/`)**
- `.less_tokens/config/budget.json` — mode, total context budget, category limits, hard caps, and per-agent overrides
- `.less_tokens/hooks/budget/` — shared budget package: candidate normalization, relevance scoring, selection, advice/enforcement outcomes, compaction snapshots, and event logging
- `.less_tokens/state/events.jsonl` — v2 telemetry for considered, selected, rejected, transformed, and compacted context
- `.less_tokens/tools/budget_report.py` — savings, omissions, transformations, quality-risk, and compaction report
- `.less_tokens/tools/budget_doctor.py` — current config and recent pressure diagnosis

**Claude Code hook layer (`.claude/hooks/`)**
- All hooks read a JSON payload from stdin and exit `0` (pass) or `2` (block/replace)
- `.claude/hooks/search-first.py` — PreToolUse on `Read` (blocks if the file is indexed and no search ran within `WINDOW_SECONDS`, 300s) and on `Grep` (non-blocking: if the pattern is a known symbol, suggests `/def` for the exact location)
- `.claude/hooks/read-guard.py` — PreToolUse on `Read`; blocks an un-sliced Read of a noise file (lockfile/minified/binary/oversized data) per `READ_DENY_GLOBS` + `READ_DENY_DATA_MAX_LINES`; a Read with an `offset` is allowed
- `.claude/hooks/auto-slice.py` — PreToolUse on `Read`; if the file was a hit in the last (recent) search, blocks an un-sliced Read with the exact `Read(offset, limit)` for the matched range (`STATE_DIR/last-search.json`, written by `search.py`); pass `offset` to override
- `.claude/hooks/index-refresh.py` — PostToolUse on `Edit|Write`; fires `embeddings.py refresh` as a detached background process; logs to `.claude/state/index-refresh.log`
- `.claude/hooks/truncate-output.py` — PostToolUse on `Bash|Read|WebFetch`; caps output at `MAX_TOOL_OUTPUT_CHARS`, scaled by `AGENT_MODEL` for Claude when configured. Bash uses head+tail lines; other tools use a 60/40 char split. Codex's adapter uses separate `CODEX_MAX_*` caps.
- `.claude/hooks/compact-trigger.py` — PostToolUse on `.*`; checks `transcript_path` size against `MAX_SESSION_CHARS`, scaled by `AGENT_MODEL` for Claude when configured; 25% hysteresis via `.claude/state/compact-trigger-last`
- `.claude/hooks/caveman-reminder.py` — Stop hook for terse output; reads the last assistant turn from `transcript_path` and exits 2 if it contains filler or exceeds `MAX_RESPONSE_WORDS` (code fences exempt); `stop_hook_active` guard prevents loops
- `.claude/hooks/claudemd-budget.py` — PostToolUse on `Edit|Write`; blocks when CLAUDE.md exceeds `CLAUDE_MD_TOKEN_BUDGET` or gains a stale ref

**Codex hook layer (`agents/codex/hooks/`)**
- Thin adapters normalize Codex payloads, call shared checks where available, and write state under `.less_tokens/state/`.
- Codex installs use `.less_tokens/tools/` compatibility shims so the single `.claude/tools/` implementation remains the source of truth while Codex commands still work from `.less_tokens/bin/python`.
- Codex filesystem matchers are broader (`mcp__filesystem__.*`) than Claude's named `Read|Grep|Glob` events, so adapters map read/search-like payloads into the shared `HookPayload` shape before running gates.
- Codex patch edits may arrive as `apply_patch`; `payload.py` extracts touched paths from patch headers so index refresh and post-edit diff logic can stay targeted instead of refreshing conservatively.
- Codex output-style enforcement uses `terse-reminder.py` as a best-effort adapter rather than Claude's direct `Stop` hook.
- Default adapters cover search-first, read guard, auto-slice, grep-first read, read-after-edit, context cache, listing guard, lean-output, post-edit diff, index refresh, AGENTS.md budget checks, truncation, compaction, and terse-output reminders.
- Event matchers and optional/default status live in `agents/common/hooks/hook_manifest.py`; shipped/missing parity lives in `agents/common/hooks/parity.json`.

**Rules (`.claude/rules/`)**
- `.claude/rules/caveman.md` — terse output style guide; append to `CLAUDE.md` with the backward-compatible `--caveman` install flag
- Audit always-loaded or appendable rule files with `.claude/bin/python .claude/tools/claudemd_audit.py --rules`; the per-file default cap is `RULES_TOKEN_BUDGET`.

**Skills (`.claude/skills/`)**
- `.claude/skills/bug-hunt/SKILL.md` — bug-hunt protocol: severity rubric, stop rule, agent prompt template
- `.claude/skills/claudemd/SKILL.md` — prune CLAUDE.md to only what must be always-loaded

**Doc and skill generation (`--check` wired into pre-commit)**
Registries and shared templates are the source of truth; renderer scripts update checked-in outputs and verify them with `--check`.
- `.claude/tools/bug_hunt_registry.py` — `SEVERITY_TIERS`, `TARGET_FILES`, `OVERLAP_THRESHOLD`/`COVERAGE_THRESHOLD`, `PROMPT_TEMPLATE`, `ROUND_REQUIRED_KEYS`; single source for the bug-hunt protocol
- `.claude/tools/bug_hunt_docs.py` — renders/verifies `agents/common/bug-hunt-protocol.md`'s severity-rubric, thresholds, target-files, and prompt-template blocks from the registry
- `.claude/tools/hunt_round.py` — validates a round JSON record (sequential round number, known severity tiers, severity sum matches `bugs_surfaced`, `overlap.matched <= overlap.total`), appends it to `.claude/skills/bug-hunt/bughuntlog.jsonl`, and scores it via `hunt_score.py` in one command
- `.claude/tools/hunt_score.py` — evaluates severity slide, overlap, and file-coverage signals from `bughuntlog.jsonl`; imports its constants from `bug_hunt_registry.py` rather than hardcoding them
- `.claude/tools/strategy_registry.py` — `STRATEGIES` (name, how, savings claim, flag/default, `savings_log` telemetry key or `None`); single source for the README strategy table and `label_consistency_gate.py`'s label map
- `.claude/tools/strategy_table_docs.py` — renders/verifies README.md's `<!-- strategy-table: begin/end -->` block from `strategy_registry.py`
- `.claude/tools/hook_parity_docs.py` — renders/verifies README.md and DOCUMENTATION.md's `<!-- hook-parity: begin/end -->` blocks from `hook_manifest.py` and `parity.json`
- `agents/common/skills/less-tokens/SKILL.md.template` — shared search, symbol, read-guard, instruction-audit, context-pack, document-draft, and index-refresh manual for both agents
- `agents/common/skills/less-tokens/{claude,codex}-delegation.md` — explicit platform overlays for divergent subagent mechanics
- `.claude/tools/less_tokens_skill_docs.py` — renders/verifies both checked-in `less-tokens` skills from the shared template and declared platform values

Hooks are unit-tested by importing them as modules via `.claude/tests/conftest.py:load_hook()` (it puts `.claude/tools/` on `sys.path` so the source tools are importable during tests, then execs the hook file). Keep hook logic importable — no side effects at module load.

### Token-reduction strategy

The mission is fewer tokens. Every token falls in one of three buckets, and each lever targets one:

- **Input** — files read, search results, history. Biggest lever (5–10×). Attacked by search-first, auto-slice, grep-first, the symbol index.
- **Output** — assistant prose. Attacked by the terse-output Stop hook.
- **Tool** — raw Bash/Read/WebFetch dumps. Attacked by truncation and the lean-output parsers.

Two principles decide *how*:

- **Code over reasoning.** When a deterministic script can produce the answer, don't make the model read and think to get there — locate a symbol, slice a file, parse test output in code.
- **Hooks enforce what prose can only request.** PreToolUse blocks the wasteful action; PostToolUse rewrites or trims the result. Unenforced instructions are useful guidance, but they are less reliable than an executable hook.

Shipped strategies (IDs are stable across `CHANGELOG.md` / `BACKLOG.md`):

| ID | Lever | What | Enforced by |
|---|---|---|---|
| S8 | input | symbol index + `/def` locate | PreToolUse Read/Grep → `symbols.py` |
| S9 | input | auto-slice Read to the searched range | PreToolUse Read → `auto-slice.py` |
| S10 | input | post-Edit diff, block the verify re-Read | Pre+PostToolUse Edit |
| S11 | output | terse-output check on the assistant turn | Stop → `caveman-reminder.py` |
| S12 | tool | structured parsers (pytest/ruff/eslint/git) | PostToolUse Bash → `lean-output.py` |
| S13 | input | grep-first: block oversized Read, route to search/symbol | PreToolUse Read |
| S14 | fixed | `instruction_prune.py`: move/pointer/re-audit/verify-recall CLAUDE.md/AGENTS.md sections | manual invocation via claudemd/agentsmd skills |

S6 (tiered effort by model) was decided against — no hook can force a per-turn model downshift, so its saving is unverified and the shipped caveman Stop hook already captures output-token savings deterministically; see `DECISIONS.md` → *Rejected*.

Deliberately rejected as periphery (no effect on context tokens): a search REPL / file-watcher, an *embedding-result* cache (saves embedding compute, not tokens), and search-quality logging. The live savings HTML artifact is intentionally included because it reports the measured local savings log; it is not a separate optimization lever.

**Reopened 2026-07-04:** the "query/result cache" line above conflated two different things. Caching *embeddings* is correctly rejected — it saves local compute, not context tokens. But a same-session cache of *identical repeated `search.py` invocations* is a different claim: skipping the rerun would also skip its tool-output round-trip re-entering the transcript, which **is** a context-token saving with both sides of the cut known (`basis="measured"`, same as `context-cache-read`/`-grep`/`-bash`). **Resolved 2026-07-07:** real `near_misses.jsonl` instrumentation for this (shipped 2026-07-05) shows zero genuine same-session repeats after ~2 days live; mining the longer-window `search-history.log` independently corroborates it — of 83 real queries in the actively-dogfooded `../less_tokens` client repo's log, only 3 repeated within a plausible same-session window (≈3–4% repeat rate). Rare; stays periphery. Full evidence: `DECISIONS.md` → *Rejected*.

### State directory

`active_state_dir()` in `search_config.py` selects the agent state directory. Claude uses `.claude/state/`; Codex uses `.less_tokens/state/`; `LESS_TOKENS_STATE_DIR` can override either for tests or advanced setups.

### Chunking strategies

| File type | Strategy | Key unit |
|---|---|---|
| `.py` | `chunk_python` — AST parse | top-level `def`/`class`/`UPPER_CASE` |
| `.js`/`.jsx`/`.ts`/`.tsx` | `chunk_js` — declaration scan | functions/classes/consts/interfaces/enums/types |
| `.md` | `chunk_markdown` — regex H1/H2/H3 | heading sections |
| `CHANGELOG.md` | `chunk_changelog` — version/date headers | Keep a Changelog and date headers |
| `.sql` | `chunk_sql` — split on `;\n` | CREATE TABLE/VIEW/INDEX name |

### End-to-end verification

For hook behavior and the full install path, verify against a scratch project:

```bash
# Install into a scratch project. The installer targets the parent of this clone — cwd doesn't matter.
python3 install.py
# Override the target:
python3 install.py --target /path/to/scratch --yes
# Build the local index (requires fastembed)
.claude/bin/python .claude/tools/embeddings.py refresh
# Search
.claude/bin/python .claude/tools/search.py "your query"
.claude/bin/python .claude/tools/search.py "query" --source-type code -k 5 --json
# Index health
.claude/bin/python .claude/tools/embeddings.py health
.claude/bin/python .claude/tools/db.py verify
```

## Moved from CLAUDE.md

## Project purpose

A **toolkit** whose job is to be installed *into other projects*: `install.py` targets a host project's parent dir and deploys `.claude/` (tools, hooks, schema, venv, `index.db`); re-run after `git pull` to upgrade in place. That is the primary mission.

But it is also developed **and dogfooded here** — this repo runs its own hooks, search, and skills to spend fewer tokens while building less_tokens. When working in this repo, use the installed tooling (search before Read, the skills, the budget hooks), not just edit it. Strategies include vector search, terse-output enforcement, tool-output truncation, session compaction, and per-agent budget controls. Deploy mechanics: `DOCUMENTATION.md`.

## Moved from AGENTS.md

## Token Discipline

Use targeted context. Prefer `rg`, `rg --files`, semantic search, and file slices over full-file reads.

Search before reading large or indexed files; use symbol lookup for definitions.

Check lockfiles, generated bundles, binaries, and large data files before reading them in full.

Directory navigation: prefer `rg --files` over recursive listings.

Responses: direct findings, exact file:line references, no filler.

Terse mode does not apply to a document/report/proposal the user asked for — see the
`less-tokens` skill for the exemption marker.

For installed commands and AGENTS.md hygiene, use the `less-tokens` skill.
<!-- less_tokens: end -->
