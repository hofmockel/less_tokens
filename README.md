# less_tokens

**Cut Claude and Codex token usage with drop-in strategies: semantic search over your codebase, search-before-read hooks, auto-sliced reads, noisy-output guards, terse-output enforcement, proactive session compaction, and instruction-file pruning.**

![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)
![Claude Code](https://img.shields.io/badge/Claude-Code-orange)
![Codex](https://img.shields.io/badge/Codex-supported-green)

---

## What it does

Agent token waste comes from several sources: reading entire files when only a few lines are relevant, rereading files already in context, dumping recursive directory listings or test output, verbose responses full of filler, conversation history that compounds turn after turn, and ever-growing `CLAUDE.md` / `AGENTS.md` files that are loaded on every turn. `less_tokens` attacks all of them.

| Strategy | How | Savings | Flag |
|---|---|---|---|
| **Vector search + symbols** | Pre-embeds source files; exact `/def` lookup for Python and JS/TS symbols | 5–10× fewer input tokens | always on |
| **Read guards** | Search-first, auto-slice, grep-first, noise-file, context-cache, and post-edit reread gates | large-file Reads become small slices | always on |
| **Lean tool output** | Parses pytest/ruff/eslint/git output and blocks recursive listing dumps | 40–90% fewer tool-output chars | always on |
| **Caveman / terse mode** | Claude Stop hook and Codex terse reminder reduce filler prose | 30–60% fewer output tokens | `--caveman` |
| **Tool output truncation** | PostToolUse hook caps oversized Bash/Read/WebFetch/filesystem results | 40–80% fewer tool-output tokens | `--truncate` |
| **Compaction trigger** | PostToolUse hook nudges `/compact` when session transcript grows large | 50–70% fewer input tokens on long sessions | `--compact` |
| **Instruction pruning** | `CLAUDE.md` and `AGENTS.md` budget audits keep always-loaded files small | eliminates per-turn always-loaded tax | always on |

Core search/read guards are wired by default for the selected agent; truncation, compaction, and caveman/terse output enforcement remain optional flags. A built-in **savings tracker** (`.claude/tools/stats.py` after install) measures chars and estimated tokens saved per strategy; off by default, enable with one command. A `.claudeignore` file is also included to keep documentation, CI config, and other non-code files out of Claude's project file scope.

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

Claude artifacts land under `.claude/`; Codex support also installs a small `.less_tokens/` runtime plus `AGENTS.md` guidance:

```
~/myproject/
├── .claude/
│   ├── .venv-tokens/        # fastembed + numpy
│   ├── bin/python           # venv-backed launcher for Claude commands
│   ├── hooks/               # Claude Code hook scripts
│   ├── index.db             # vector index
│   ├── rules/               # output style rules (caveman.md) — --caveman only
│   ├── schema/              # SQL schema
│   ├── skills/claudemd/     # /claudemd CLAUDE.md pruning skill
│   ├── state/               # runtime state (last-search, savings log, …)
│   └── tools/               # search.py, embeddings.py, db.py, stats.py, …
├── .less_tokens/            # Codex shims/hooks/state when --agent codex|both
│   ├── hooks/               # shared hook support used by Codex adapters
│   ├── bin/python           # venv-backed launcher for Codex commands
│   ├── schema/
│   ├── skills/less-tokens/  # fallback Codex skill path
│   ├── state/
│   └── tools/               # shims into .claude/tools/
├── .codex/hooks/            # Codex adapter hooks, when .codex is writable
├── .codex/hooks.json        # Codex hook wiring, when .codex is writable
├── AGENTS.md                # Codex token-discipline block
└── less_tokens/             # this clone — unchanged after install
```

Upgrade an existing install the same way:

```bash
cd ~/myproject/less_tokens && git pull
python3 install.py --update                # safe re-copy of hooks + tools
```

See [documentation.md](documentation.md) for full installation, configuration, usage, and hook wiring instructions. See [codex-hook-coverage.md](codex-hook-coverage.md) for the exact Codex hook matrix.

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
