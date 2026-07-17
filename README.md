# less_tokens  

**Cut Claude and Codex token usage with drop-in strategies: semantic search over your codebase, a budget-native context control plane, search-before-read hooks, auto-sliced reads, noisy-output guards, terse-output enforcement, proactive session compaction, and instruction-file pruning.**

> [!TIP]
> ### [Open the full HTML documentation →](https://hofmockel.github.io/less_tokens/)
> Explore the visual strategy map, installation and configuration guides, architecture, telemetry, troubleshooting, and the subagent-support roadmap.

![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)

![Human](https://img.shields.io/badge/made_by-Human-pink)
![Claude Code](https://img.shields.io/badge/Claude-Code-orange)
![Codex](https://img.shields.io/badge/Codex-supported-green)

[![Tests](https://github.com/hofmockel/less_tokens/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/hofmockel/less_tokens/actions/workflows/tests.yml)
[![Install E2E](https://github.com/hofmockel/less_tokens/actions/workflows/install-e2e.yml/badge.svg?branch=main)](https://github.com/hofmockel/less_tokens/actions/workflows/install-e2e.yml)
[![Stats](https://github.com/hofmockel/less_tokens/actions/workflows/stats.yml/badge.svg?branch=main)](https://github.com/hofmockel/less_tokens/actions/workflows/stats.yml)
[![CodeQL](https://github.com/hofmockel/less_tokens/actions/workflows/codeql.yml/badge.svg?branch=main)](https://github.com/hofmockel/less_tokens/actions/workflows/codeql.yml)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Local Only](https://img.shields.io/badge/data-local--only-2ea44f)

---

## What it does

Agent token waste comes from several sources: reading entire files when only a few lines are relevant, rereading files already in context, dumping recursive directory listings or test output, verbose responses full of filler, conversation history that compounds turn after turn, and ever-growing `CLAUDE.md` / `AGENTS.md` files that are loaded on every turn. `less_tokens` attacks all of them.

<!-- strategy-table: begin -->
| Strategy | How | Savings | Flag |
|---|---|---|---|
| **Budget control plane** | Scores, replaces, defers, or blocks context before it enters the agent transcript; writes v2 telemetry and reports | avoids irrelevant context before it is paid for | always on |
| **Vector search + symbols** | Pre-embeds source files; exact symbol lookup for Python and JS/TS via `symbols.py` (`/def` only when slash commands are installed) | 5–10× fewer input tokens | always on |
| **Read guards** | Search-first, auto-slice, grep-first, noise-file, context-cache, and post-edit reread gates | large-file Reads become small slices | always on |
| **Lean tool output** | Parses pytest/ruff/eslint/git output and blocks recursive listing dumps | 40–90% fewer tool-output chars (not telemetry-backed — no savings.jsonl category) | always on |
| **Terse output mode** | Claude Stop hook and Codex terse reminder reduce filler prose | 30–60% fewer output tokens (not telemetry-backed — no baseline to diff against) | default; opt out with `--no-caveman` |
| **Tool output truncation** | PostToolUse hook caps oversized Bash/Read/WebFetch/filesystem results | 40–80% fewer tool-output tokens | default; opt out with `--no-truncate` |
| **Compaction trigger** | PostToolUse hook nudges `/compact` (Claude) or a fresh/compacted session (Codex) when session transcript grows large | 50–70% fewer input tokens on long sessions | default; opt out with `--no-compact` |
| **Instruction pruning** | `CLAUDE.md` and `AGENTS.md` budget audits keep always-loaded files small | eliminates per-turn always-loaded tax | always on |
<!-- strategy-table: end -->

Core search/read guards, lean-output hooks, truncation, compaction nudges, terse-output enforcement, and the budget control plane are wired by default for the selected agent when the target hook location is writable; Codex wiring remains best-effort and falls back to `AGENTS.md` + skills if `.codex/` isn't writable. Use `--no-truncate`, `--no-compact`, or `--no-caveman` to opt out of those default savings hooks.

Claude and Codex have feature parity for shipped strategies, but they do not have identical enforcement. Claude hooks are enforced directly. Codex enforcement is best-effort through `.codex/hooks.json`, using Codex CLI's nested matcher-group schema (`hooks` → groups → matchers → command hooks). That difference is intentional: Claude has extra reliable levers, including direct hooks, `agent_overrides.claude`, and model-aware thresholds. Those Claude-only settings are isolated so they can cut Claude token use without changing Codex behavior.

A built-in **savings tracker** (`.claude/tools/stats.py` for Claude; `.less_tokens/tools/stats.py` shim for Codex) measures chars and estimated tokens saved per strategy. Tracking is always on, local-only, and written to the active state directory: `.claude/state/savings.jsonl` for Claude and `.less_tokens/state/savings.jsonl` for Codex. Nothing is transmitted. Disable tracking with `LESS_TOKENS_NO_STATS=1`. A `.claudeignore` file is also included to keep documentation, CI config, and other non-code files out of Claude's project file scope.

**Claude vs Codex support**

<!-- hook-parity: begin -->

Feature parity means the same strategy is shipped for both agents. Enforcement parity is intentionally different: Claude hooks are direct enforcement, while Codex hooks are best-effort adapters through `.codex/hooks.json`.

| Strategy | Feature parity | Claude enforcement | Codex enforcement |
|---|---|---|---|
| `budget-observer` | yes | enforced; `.claude/hooks/budget-observer.py`; PreToolUse `Read|Grep|Glob|Bash`, PostToolUse `Read|Grep|Glob|Bash|Edit|Write` | best-effort; `.codex/hooks/budget-observer.py`; PreToolUse `mcp__filesystem__.*|Bash`, PostToolUse `Bash|mcp__filesystem__.*|apply_patch|Edit|Write` |
| `search-first` | yes | enforced; `.claude/hooks/search-first.py`; PreToolUse `Read`, PreToolUse `Grep` | best-effort; `.codex/hooks/search-first.py`; PreToolUse `mcp__filesystem__.*` |
| `read-guard` | yes | enforced; `.claude/hooks/read-guard.py`; PreToolUse `Read` | best-effort; `.codex/hooks/read-guard.py`; PreToolUse `mcp__filesystem__.*` |
| `auto-slice` | yes | enforced; `.claude/hooks/auto-slice.py`; PreToolUse `Read` | best-effort; `.codex/hooks/auto-slice.py`; PreToolUse `mcp__filesystem__.*` |
| `grep-first-read` | yes | enforced; `.claude/hooks/grep-first-read.py`; PreToolUse `Read` | best-effort; `.codex/hooks/grep-first-read.py`; PreToolUse `mcp__filesystem__.*` |
| `read-after-edit` | yes | enforced; `.claude/hooks/read-after-edit.py`; PreToolUse `Read` | best-effort; `.codex/hooks/read-after-edit.py`; PreToolUse `mcp__filesystem__.*` |
| `continue-freshness` | yes | enforced; `.claude/hooks/continue-freshness.py`; PreToolUse `Read` | best-effort; `.codex/hooks/continue-freshness.py`; PreToolUse `mcp__filesystem__.*` |
| `context-cache` | yes | enforced; `.claude/hooks/context-cache.py`; PreToolUse `Read|Grep`, PostToolUse `Read|Grep` | best-effort; `.codex/hooks/context-cache.py`; PreToolUse `mcp__filesystem__.*|Bash`, PostToolUse `Bash`, PostToolUse `mcp__filesystem__.*` |
| `post-edit-diff` | yes | enforced; `.claude/hooks/post-edit-diff.py`; PostToolUse `Edit|Write` | best-effort; `.codex/hooks/post-edit-diff.py`; PostToolUse `apply_patch|Edit|Write` |
| `index-refresh` | yes | enforced; `.claude/hooks/index-refresh.py`; PostToolUse `Edit|Write` | best-effort; `.codex/hooks/index-refresh.py`; PostToolUse `apply_patch|Edit|Write` |
| `agent-md-budget` | yes | enforced; `.claude/hooks/claudemd-budget.py`; PostToolUse `Edit|Write` | best-effort; `.codex/hooks/agentsmd-budget.py`; PostToolUse `Edit|Write` |
| `lean-output` | yes | enforced; `.claude/hooks/lean-output.py`; PostToolUse `Bash` | best-effort; `.codex/hooks/lean-output.py`; PostToolUse `Bash` |
| `listing-guard` | yes | enforced; `.claude/hooks/listing-guard.py`; PreToolUse `Bash` | best-effort; `.codex/hooks/listing-guard.py`; PreToolUse `Bash` |
| `truncate-output` | yes; default-on optional | enforced; `.claude/hooks/truncate-output.py`; PostToolUse `Bash|Read|WebFetch|Glob` | best-effort; `.codex/hooks/truncate-output.py`; PostToolUse `Bash|mcp__filesystem__.*` |
| `subagent-cap` | Claude only; default-on optional | enforced; `.claude/hooks/subagent-cap.py`; PostToolUse `Task` | missing |
| `subagent-fanout` | Claude only | enforced; `.claude/hooks/subagent-fanout.py`; PreToolUse `Task`, PostToolUse `Task` | missing |
| `compact-trigger` | yes; default-on optional | enforced; `.claude/hooks/compact-trigger.py`; PostToolUse `.*` | best-effort; `.codex/hooks/compact-trigger.py`; PostToolUse `.*` |
| `terse-output` | yes; default-on optional | enforced; `.claude/hooks/caveman-reminder.py`; Stop `*`, SubagentStop `*` | best-effort; `.codex/hooks/terse-reminder.py`; PostToolUse `.*` |
| `savings-html` | yes | enforced; `.claude/hooks/savings-html.py`; Stop `*`, SubagentStop `*` | best-effort; `.codex/hooks/savings-html.py`; PostToolUse `.*` |

<!-- hook-parity: end -->

```
Without less_tokens:           With less_tokens:
Read(large_file.py)            search.py "validate imports"
→ 5,000 tokens                 → 3 chunks × ~150 tokens = 450 tokens
```

Files are chunked by structure (functions, headings, SQL statements, JS/TS declarations), embedded locally using [`BAAI/bge-small-en-v1.5`](https://huggingface.co/BAAI/bge-small-en-v1.5), and stored in a local SQLite database. No data leaves your machine.

## Subagent support

`less_tokens` supports delegated work without pretending every agent exposes the same controls.

| Surface | Shipped support |
|---|---|
| **Claude** | `subagent-cap` trims oversized `Task` returns to key fields or a bounded head/tail digest; `subagent-fanout` measures prompt and return size for every observed spawn. |
| **Codex** | The installed `less-tokens` skill provides explicit, pointer-first delegation templates and compact return contracts. Codex has no equivalent repo-hookable `Task` boundary, so automatic return capping and fan-out telemetry are not claimed. |

Claude's return cap defaults to 6,000 characters and follows the default-on truncation setting (`--no-truncate` opts out). Fan-out telemetry is measurement-only and always wired: reports show spawn count, prompt characters sent, and return characters absorbed by the parent, separately from token-savings totals.

The roadmap is evidence-gated: SA3 may filter oversized spawn prompts only if SA2 shows prompt-side waste is material; SA4 may isolate budget state per child only if live payloads expose distinct session IDs and concurrency risk; SA5 may add role-specific digests only if at least two roles show a measurable advantage over SA1; SA6 stays parked unless a future harness replays full child transcripts to the parent. See [DOCUMENTATION.md → Subagent support](DOCUMENTATION.md#subagent-support) for the canonical reference or the [HTML Subagent Support page](docs-site/site/reference/subagents.html) for the visual summary.

---

## Quick start

Clone this repo *into* the project you want to install it on, then run the installer — it targets the parent directory of the clone, so cwd doesn't matter:

```bash
cd ~/myproject
git clone https://github.com/<you>/less_tokens.git
python3 less_tokens/install.py            # Claude Code (default)
python3 less_tokens/install.py --agent codex   # Codex
python3 less_tokens/install.py --agent both    # both simultaneously
```

`.claude/` holds shared implementation and index artifacts (tools, schema, `index.db`) used by both agents, not just Claude-only files; the shared budget control plane lives under `.less_tokens/`, and Codex support adds adapter hooks under `.codex/` (when writable) plus `AGENTS.md`. Full directory tree: [DOCUMENTATION.md → Repository layout](DOCUMENTATION.md#repository-layout).

Upgrade an existing install the same way:

```bash
cd ~/myproject/less_tokens && git pull
python3 install.py --update --agent claude   # safe re-copy of Claude hooks + tools
python3 install.py --update --agent codex    # safe re-copy + Codex hooks.json migration
python3 install.py --update --agent both     # update both integrations
```

The Codex update path automatically replaces the pre-CX21 flat `.codex/hooks.json` layout with the nested structure required by current `codex-cli`, while preserving unrelated entries that already use the valid nested shape. No manual JSON edit is required.

See [DOCUMENTATION.md](DOCUMENTATION.md) for full installation, configuration, usage, hook wiring instructions, and the Claude/Codex parity matrix. The hook manifest lives in [`agents/common/hooks/hook_manifest.py`](agents/common/hooks/hook_manifest.py), with CI-checked parity data in [`agents/common/hooks/parity.json`](agents/common/hooks/parity.json).

Budget behavior is controlled by `.less_tokens/config/budget.json`. Modes are `observe` (record only), `advise` (print concise suggestions), `enforce` (block actionable waste with a replacement or bypass), and `strict` (also blocks oversized unscored context). The project config also supports per-agent overrides; Claude and Codex can use different category limits and hard caps without changing the shared defaults. Inspect recent decisions with:

```bash
.claude/bin/python .less_tokens/tools/budget_report.py
.claude/bin/python .less_tokens/tools/budget_doctor.py
```

---

## Install via AI agent (easiest)

Open Claude Code (or any agent with web access) in your project directory and paste:

```
install https://github.com/hofmockel/less_tokens/blob/main/README.md
```

Agent reads the README, clones the repo, and runs the installer. No manual steps.

---

## Contributing

Fork, add an entry to [BACKLOG.md](BACKLOG.md), and open a PR. Code-changing PRs should also add an `[Unreleased]` entry to `CHANGELOG.md`.

---

## License

MIT
