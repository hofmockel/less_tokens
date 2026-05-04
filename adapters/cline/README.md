# Cline Adapter

Use `less_tokens` strategies in [Cline](https://cline.bot) (the VS Code extension), not just Claude Code.

## What ports

| Strategy | Cline mechanism | Status |
|---|---|---|
| 1 — Vector search | MCP tool (`search`) + `.clinerules/01-search-before-read.md` | Ships |
| 2 — Caveman mode | `.clinerules/02-caveman.md` | Ships |
| 3 — Tool output truncation | PostToolUse hook (`hooks/truncate-output.py`) | Hook reusable; wiring requires payload probe (below) |
| 5 — Compaction trigger | PostToolUse hook (`hooks/compact-trigger.py`) | Hook reusable; wiring requires payload probe |
| 6 — Tier matrix | `.clinerules/03-tier-matrix.md` | Lands when Strategy 6 ships in main repo |

## Install

```bash
# 1. Run the base installer first (copies tools/, builds index, etc.)
python3 path/to/less_tokens_claude/install.py

# 2. Run the Cline adapter installer
python3 path/to/less_tokens_claude/adapters/cline/install-cline.py
```

The adapter installer:

1. Copies `clinerules/*.md` into your project's `.clinerules/` directory.
2. Patches `tools/search_config.py` to set `STATE_DIR = .less_tokens/state/` (so Cline projects don't get a stray `.claude/` directory).
3. Installs the `mcp` Python SDK into your project venv.
4. Prints the `cline_mcp_settings.json` snippet you need to merge.

## Register the MCP server

Cline's MCP config is **user-level**, not project-level. The installer prints the exact path for your OS:

| OS | `cline_mcp_settings.json` path |
|---|---|
| macOS | `~/Library/Application Support/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json` |
| Linux | `~/.config/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json` |
| Windows | `%APPDATA%/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json` |

Merge the printed entry into `mcpServers`. Reload the VS Code window for Cline to pick up the new server.

## Hooks (advanced)

Cline supports the same hook surface as Claude Code (PreToolUse, PostToolUse, PreCompact, etc.) and the payload shape appears compatible. To wire `truncate-output.py` and `compact-trigger.py`:

### Verification probe

Before depending on the existing hook logic, confirm Cline's payload field names match:

```bash
# Add a temporary debug line at the top of hooks/truncate-output.py main():
#   import json, sys; open('/tmp/cline-payload.json', 'w').write(sys.stdin.read()); sys.exit(0)
# Wire it as a PostToolUse hook in Cline's hook config.
# Trigger any tool, then inspect /tmp/cline-payload.json.
# Confirm: tool_name, tool_result, transcript_path field names match.
```

If field names match, wire the hooks directly. If they differ, write a thin shim hook that reshapes the payload and calls the existing hook — the hook *logic* doesn't need to fork.

For the exact Cline hook config schema, see [Cline hooks docs](https://docs.cline.bot/customization/hooks).

## What doesn't port

- **Project-level MCP config** — Cline only supports user-level MCP registration. Track [this issue](https://github.com/cline/cline/discussions) if you need per-project servers.
- **Auto-condense overlap** — Cline has built-in `useAutoCondense` that overlaps with our compact-trigger hook. Pick one or tune both thresholds; don't run them both at default settings.

## Files

```
adapters/cline/
├── README.md                       # this file
├── install-cline.py                # adapter installer
├── clinerules/
│   ├── 01-search-before-read.md   # search-first instruction
│   └── 02-caveman.md              # terse output instruction
└── mcp-search/
    ├── server.py                   # FastMCP stdio server exposing search()
    └── pyproject.toml              # `mcp` SDK dependency
```
