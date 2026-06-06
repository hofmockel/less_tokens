# less_tokens

**Cut Claude's token usage with four drop-in strategies: semantic search over your codebase, enforced terse output, tool result truncation, and proactive session compaction.**

![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)
![Claude Code](https://img.shields.io/badge/Claude-Code-orange)

---

## What it does

Claude's token waste comes from four sources: reading entire files when only a few lines are relevant, verbose responses full of filler, tool results that dump thousands of characters into context, and conversation history that compounds turn after turn. `less_tokens` attacks all four.

| Strategy | How | Savings |
|---|---|---|
| **Vector search** | Pre-embeds your source files; Claude searches before reading | 5–10× fewer input tokens |
| **Caveman mode** | CLAUDE.md instruction that enforces terse, primitive output | 30–60% fewer output tokens |
| **Tool output truncation** | PostToolUse hook caps oversized Bash/Read/WebFetch results | 40–80% fewer tool-output tokens |
| **Compaction trigger** | PostToolUse hook nudges `/compact` when session transcript grows large | 50–70% fewer input tokens on long sessions |

All four strategies are opt-in and independent — use any combination. A built-in **savings tracker** (`.claude/tools/stats.py` after install) measures chars and estimated tokens saved per strategy; off by default, enable with one command. A `.claudeignore` file is also included to keep documentation, CI config, and other non-code files out of Claude's project file scope.

```
Without less_tokens:           With less_tokens:
Read(large_file.py)            search.py "validate imports"
→ 5,000 tokens                 → 3 chunks × ~150 tokens = 450 tokens
```

Files are chunked by structure (functions, headings, SQL statements), embedded locally using [`BAAI/bge-small-en-v1.5`](https://huggingface.co/BAAI/bge-small-en-v1.5), and stored in a local SQLite database. No data leaves your machine.

---

## Quick start

Clone this repo *into* the project you want to install it on, then run the installer — it targets the parent directory of the clone, so cwd doesn't matter:

```bash
cd ~/myproject
git clone https://github.com/<you>/less_tokens.git
python3 less_tokens/install.py            # installs into ~/myproject
```

After install, all artifacts land under `.claude/` to keep the project root clean:

```
~/myproject/
├── .claude/
│   ├── .venv-tokens/   # fastembed + numpy
│   ├── hooks/          # Claude Code hook scripts
│   ├── index.db        # vector index
│   ├── rules/          # output style rules (caveman.md)
│   ├── schema/         # SQL schema
│   ├── state/          # runtime state (last-search, savings log, …)
│   └── tools/          # search.py, embeddings.py, db.py, stats.py, …
└── less_tokens/        # this clone — unchanged after install
```

Upgrade an existing install the same way:

```bash
cd ~/myproject/less_tokens && git pull
python3 install.py --update                # safe re-copy of hooks + tools
```

See [documentation.md](documentation.md) for full installation, configuration, usage, and hook wiring instructions.

---

## Contributing

Fork, add an entry to [BACKLOG.md](BACKLOG.md), open a PR. See [CONTRIBUTING.md](CONTRIBUTING.md) for the workflow.

---

## License

MIT
