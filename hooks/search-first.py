#!/usr/bin/env python3
"""PreToolUse hook: enforce search-before-Read on indexed files.

Receives the tool call JSON on stdin. Exits 2 with a stderr message to feed
back to the model when an indexed file is being Read without a recent search.
The agent can satisfy the gate by running:

    app/.venv/bin/python tools/search.py "QUERY"

That touches .claude/state/last-search; subsequent Reads within WINDOW_SECONDS
are allowed.

Configured in .claude/settings.local.json:

    {
      "hooks": {
        "PreToolUse": [
          {"matcher": "Read",
           "hooks": [{"type": "command",
                      "command": "python3 .claude/hooks/search-first.py"}]}
        ]
      }
    }
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "tools"))
from search_config import (  # noqa: E402
    EXCLUDED_DIR_PREFIXES as EXCLUDED_DIRS,
    INDEXED_ROOT_GLOBS,
    INDEXED_SOURCE_DIRS as INDEXED_DIRS,
)

STATE_FILE = REPO / ".claude" / "state" / "last-search"
WINDOW_SECONDS = 300


def is_indexed(path: Path) -> bool:
    try:
        rel = path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return False
    if any(("/" + d) in ("/" + rel) or rel.startswith(d) for d in EXCLUDED_DIRS):
        return False
    if "/" not in rel:
        # Repo-root file: only Markdown is indexed.
        return rel.endswith(".md")
    if any(rel.startswith(d) for d in INDEXED_DIRS):
        return rel.endswith((".py", ".sql", ".md"))
    return False


def search_was_recent() -> bool:
    if not STATE_FILE.exists():
        return False
    return (time.time() - STATE_FILE.stat().st_mtime) < WINDOW_SECONDS


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    if payload.get("tool_name") != "Read":
        return 0
    file_path = payload.get("tool_input", {}).get("file_path", "")
    if not file_path:
        return 0

    p = Path(file_path)
    if not is_indexed(p):
        return 0
    if search_was_recent():
        return 0

    rel = p.resolve().relative_to(REPO).as_posix()
    msg = (
        f"Search-first rule (CLAUDE.md): {rel} is indexed.\n"
        f"Run vector search before Read:\n"
        f"  app/.venv/bin/python tools/search.py \"<your query>\"\n"
        f"After a search, Reads on indexed files are allowed for "
        f"{WINDOW_SECONDS}s. If you need to edit this file, search first to "
        f"satisfy the gate, then Read + Edit normally."
    )
    print(msg, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
