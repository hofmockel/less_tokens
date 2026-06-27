# less_tokens

**Cut Claude and Codex token usage with drop-in strategies: semantic search over your codebase, a budget-native context control plane, search-before-read hooks, auto-sliced reads, noisy-output guards, terse-output enforcement, proactive session compaction, and instruction-file pruning.**

![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)
![Claude Code](https://img.shields.io/badge/Claude-Code-orange)
![Codex](https://img.shields.io/badge/Codex-supported-green)

---

## What it does

Agent token waste comes from several sources: reading entire files when only a few lines are relevant, rereading files already in context, dumping recursive directory listings or test output, verbose responses full of filler, conversation history that compounds turn after turn, and ever-growing `CLAUDE.md` / `AGENTS.md` files that are loaded on every turn. `less_tokens` attacks all of them.

| Strategy | How | Savings | Flag |
|---|---|---|---|
| **Budget control plane** | Scores, replaces, defers, or blocks context before it enters the agent transcript; writes v2 telemetry and reports | avoids irrelevant context before it is paid for | always on |
| **Vector search + symbols** | Pre-embeds source files; exact `/def` lookup for Python and JS/TS symbols | 5–10× fewer input tokens | always on |
| **Read guards** | Search-first, auto-slice, grep-first, noise-file, context-cache, and post-edit reread gates | large-file Reads become small slices | always on |
| **Lean tool output** | Parses pytest/ruff/eslint/git output and blocks recursive listing dumps | 40–90% fewer tool-output chars | always on |
| **Caveman / terse mode** | Claude Stop hook and Codex terse reminder reduce filler prose | 30–60% fewer output tokens | default; opt out with `--no-caveman` |
| **Tool output truncation** | PostToolUse hook caps oversized Bash/Read/WebFetch/filesystem results | 40–80% fewer tool-output tokens | default; opt out with `--no-truncate` |
| **Compaction trigger** | PostToolUse hook nudges `/compact` when session transcript grows large | 50–70% fewer input tokens on long sessions | default; opt out with `--no-compact` |
| **Instruction pruning** | `CLAUDE.md` and `AGENTS.md` budget audits keep always-loaded files small | eliminates per-turn always-loaded tax | always on |

Core search/read guards, lean-output hooks, truncation, compaction nudges, terse-output enforcement, and the budget control plane are wired by default for the selected agent; use `--no-truncate`, `--no-compact`, or `--no-caveman` to opt out of the formerly optional savings hooks. Claude and Codex have feature parity for the shipped strategies, but Codex enforcement is best-effort through `.codex/hooks.json` while Claude hooks are enforced directly. Parity is the floor, not the ceiling: every shipped strategy reaches both agents, but Claude has more enforceable levers (direct hooks, `agent_overrides.claude`, model-aware thresholds) and we deliberately push Claude ahead where a Claude-only lever cuts tokens at acceptable risk rather than throttle it to Codex's best-effort ceiling — Claude-only headroom is tracked as CL-prefixed items in `BACKLOG.md`, each isolated so it never degrades Codex. A built-in **savings tracker** (`.claude/tools/stats.py` for Claude; `.less_tokens/tools/stats.py` shim for Codex) measures chars and estimated tokens saved per strategy; always on and local-only (written to the active state dir: `.claude/state/savings.jsonl` for Claude, `.less_tokens/state/savings.jsonl` for Codex), never transmitted, disable with `LESS_TOKENS_NO_STATS=1`. A `.claudeignore` file is also included to keep documentation, CI config, and other non-code files out of Claude's project file scope.

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
| `context-cache` | yes | enforced; `.claude/hooks/context-cache.py`; PreToolUse `Read|Grep` | best-effort; `.codex/hooks/context-cache.py`; PreToolUse `mcp__filesystem__.*|Bash`, PostToolUse `Bash` |
| `post-edit-diff` | yes | enforced; `.claude/hooks/post-edit-diff.py`; PostToolUse `Edit|Write` | best-effort; `.codex/hooks/post-edit-diff.py`; PostToolUse `apply_patch|Edit|Write` |
| `index-refresh` | yes | enforced; `.claude/hooks/index-refresh.py`; PostToolUse `Edit|Write` | best-effort; `.codex/hooks/index-refresh.py`; PostToolUse `apply_patch|Edit|Write` |
| `agent-md-budget` | yes | enforced; `.claude/hooks/claudemd-budget.py`; PostToolUse `Edit|Write` | best-effort; `.codex/hooks/agentsmd-budget.py`; PostToolUse `Edit|Write` |
| `lean-output` | yes | enforced; `.claude/hooks/lean-output.py`; PostToolUse `Bash` | best-effort; `.codex/hooks/lean-output.py`; PostToolUse `Bash` |
| `listing-guard` | yes | enforced; `.claude/hooks/listing-guard.py`; PreToolUse `Bash` | best-effort; `.codex/hooks/listing-guard.py`; PreToolUse `Bash` |
| `truncate-output` | yes; default-on optional | enforced; `.claude/hooks/truncate-output.py`; PostToolUse `Bash|Read|WebFetch|Glob` | best-effort; `.codex/hooks/truncate-output.py`; PostToolUse `Bash|mcp__filesystem__.*` |
| `compact-trigger` | yes; default-on optional | enforced; `.claude/hooks/compact-trigger.py`; PostToolUse `.*` | best-effort; `.codex/hooks/compact-trigger.py`; PostToolUse `.*` |
| `terse-output` | yes; default-on optional | enforced; `.claude/hooks/caveman-reminder.py`; Stop `*` | best-effort; `.codex/hooks/terse-reminder.py`; PostToolUse `.*` |
| `savings-html` | yes | enforced; `.claude/hooks/savings-html.py`; Stop `*` | best-effort; `.codex/hooks/savings-html.py`; PostToolUse `.*` |

<!-- hook-parity: end -->

```
Without less_tokens:           With less_tokens:
Read(large_file.py)            search.py "validate imports"
→ 5,000 tokens                 → 3 chunks × ~150 tokens = 450 tokens
```

Files are chunked by structure (functions, headings, SQL statements, JS/TS declarations), embedded locally using [`BAAI/bge-small-en-v1.5`](https://huggingface.co/BAAI/bge-small-en-v1.5), and stored in a local SQLite database. No data leaves your machine.

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

Claude artifacts land under `.claude/`, the shared budget control plane under `.less_tokens/`, and Codex support adds adapter hooks plus `AGENTS.md`. Full directory tree: [DOCUMENTATION.md → Repository layout](DOCUMENTATION.md#repository-layout).

Upgrade an existing install the same way:

```bash
cd ~/myproject/less_tokens && git pull
python3 install.py --update                # safe re-copy of hooks + tools
```

See [DOCUMENTATION.md](DOCUMENTATION.md) for full installation, configuration, usage, hook wiring instructions, and the Claude/Codex parity matrix. The hook manifest lives in [`agents/common/hooks/hook_manifest.py`](agents/common/hooks/hook_manifest.py), with CI-checked parity data in [`agents/common/hooks/parity.json`](agents/common/hooks/parity.json).

Budget behavior is controlled by `.less_tokens/config/budget.json`. Modes are `observe` (record only), `advise` (print concise suggestions), `enforce` (block actionable waste with a replacement or bypass), and `strict` (also blocks oversized unscored context). Inspect recent decisions with:

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

Fork, add an entry to [BACKLOG.md](BACKLOG.md), open a PR. See [CONTRIBUTING.md](CONTRIBUTING.md) for the workflow.

---

## License

MIT
