#!/usr/bin/env python3
"""Apply .claude/.toolignore to Claude Code settings — remove ignored MCP servers.

Reads server names from .claude/.toolignore (one per line, # = comment) and
removes matching entries from mcpServers in the target settings file.

Usage:
  # Preview changes (safe)
  python .claude/tools/mcp-prune.py --dry-run

  # Apply to project settings
  python .claude/tools/mcp-prune.py --in-place .claude/settings.json

  # Apply to global settings
  python .claude/tools/mcp-prune.py --in-place ~/.claude.json

  # Print pruned JSON to stdout (redirect to file manually)
  python .claude/tools/mcp-prune.py .claude/settings.json

The .toolignore file lives at .claude/.toolignore (project root .toolignore
also accepted). Format:
  # comments are ignored
  slack          # remove this server
  github         # remove this one too

Re-adding a server: remove it from .toolignore, then re-run to restore.
Servers not present in the file are left untouched.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import BASE as _BASE  # noqa: E402


def load_toolignore(base: Path) -> set[str]:
    candidates = [base / ".claude" / ".toolignore", base / ".toolignore"]
    ignored: set[str] = set()
    for p in candidates:
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.split("#")[0].strip()
            if line:
                ignored.add(line)
    return ignored


def prune(settings_path: Path, ignored: set[str]) -> tuple[dict, list[str]]:
    """Return (pruned_data, removed_names)."""
    data = json.loads(settings_path.read_text(encoding="utf-8"))
    servers: dict = data.get("mcpServers", {})
    removed = [name for name in list(servers) if name in ignored]
    for name in removed:
        del servers[name]
    if "mcpServers" in data:
        data["mcpServers"] = servers
    return data, removed


def main() -> int:
    ap = argparse.ArgumentParser(description="Remove ignored MCP servers from settings")
    ap.add_argument(
        "settings",
        nargs="?",
        metavar="SETTINGS_FILE",
        help="Settings file to process (default: .claude/settings.json)",
    )
    ap.add_argument(
        "--in-place",
        action="store_true",
        help="Write pruned settings back to the same file",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be removed without changing anything",
    )
    ap.add_argument(
        "--ignore-file",
        metavar="PATH",
        help="Explicit .toolignore path (overrides auto-discovery)",
    )
    args = ap.parse_args()

    settings_path = (
        Path(args.settings) if args.settings else _BASE / ".claude" / "settings.json"
    )
    if not settings_path.exists():
        print(f"not found: {settings_path}", file=sys.stderr)
        return 2

    if args.ignore_file:
        ignored: set[str] = set()
        p = Path(args.ignore_file)
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    ignored.add(line)
    else:
        ignored = load_toolignore(_BASE)

    if not ignored:
        print("No entries in .toolignore — nothing to prune.")
        return 0

    pruned, removed = prune(settings_path, ignored)

    if args.dry_run:
        if removed:
            print(f"Would remove from {settings_path}:")
            for name in removed:
                print(f"  - {name}")
        else:
            print(
                f"Nothing to remove from {settings_path} (no overlap with .toolignore)."
            )
        return 0

    if not removed:
        print("Nothing to remove (no overlap with .toolignore).")
        return 0

    output = json.dumps(pruned, indent=2) + "\n"

    if args.in_place:
        settings_path.write_text(output, encoding="utf-8")
        print(f"Removed {len(removed)} server(s) from {settings_path}:")
        for name in removed:
            print(f"  - {name}")
    else:
        sys.stdout.write(output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
