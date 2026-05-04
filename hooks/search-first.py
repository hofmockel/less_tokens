#!/usr/bin/env python3
"""PreToolUse hook: enforce search-before-Read on indexed files.

Receives the tool call JSON on stdin. Exits 2 with a stderr message to feed
back to the model when an indexed file is being Read without a recent search.
The agent can satisfy the gate by running:

    <VENV_PY> tools/search.py "QUERY"

where VENV_PY is configured in tools/search_config.py.

That touches .claude/state/last-search; subsequent Reads within WINDOW_SECONDS
are allowed.

Configured in .claude/settings.local.json:

    {
      "hooks": {
        "PreToolUse": [
          {"matcher": "Read",
           "hooks": [{"type": "command",
                      "command": "<VENV_PY> .claude/hooks/search-first.py"}]}
        ]
      }
    }

Use the venv python printed by install.py — `python3` does not exist on
default Windows installs and bypasses the project venv on Unix.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent

STATE_FILE = REPO / ".claude" / "state" / "last-search"
WINDOW_SECONDS = 300


_config: dict = {}


def _load_config() -> bool:
    """Load search_config into _config. Returns False (and warns) on failure."""
    try:
        sys.path.insert(0, str(REPO / "tools"))
        from search_config import (  # noqa: E402
            EXCLUDED_DIR_PREFIXES as EXCLUDED_DIRS,
            INDEXED_ROOT_GLOBS,
            INDEXED_SOURCE_DIRS as INDEXED_DIRS,
            VENV_PY,
        )
        _config["excluded"] = EXCLUDED_DIRS
        _config["root_globs"] = INDEXED_ROOT_GLOBS
        _config["dirs"] = INDEXED_DIRS
        _config["venv_py"] = VENV_PY
        return True
    except Exception as e:
        print(f"search-first: could not load search_config ({e}); gate disabled", file=sys.stderr)
        return False


def is_indexed(path: Path) -> bool:
    try:
        rel = path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return False
    excluded = _config.get("excluded", [])
    dirs = _config.get("dirs", [])
    if any(("/" + d) in ("/" + rel) or rel.startswith(d) for d in excluded):
        return False
    if "/" not in rel:
        return rel.endswith(".md")
    if any(rel.startswith(d) for d in dirs):
        return rel.endswith((".py", ".sql", ".md"))
    return False


def search_was_recent() -> bool:
    try:
        mtime = STATE_FILE.stat().st_mtime
    except OSError:
        return False
    return (time.time() - mtime) < WINDOW_SECONDS


def main() -> int:
    if not _load_config():
        return 0  # degrade gracefully; don't block Reads

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

    venv_py = _config.get("venv_py", "python3")
    rel = p.resolve().relative_to(REPO).as_posix()
    msg = (
        f"Search-first rule (CLAUDE.md): {rel} is indexed.\n"
        f"Run vector search before Read:\n"
        f"  {venv_py} tools/search.py \"<your query>\"\n"
        f"After a search, Reads on indexed files are allowed for "
        f"{WINDOW_SECONDS}s. If you need to edit this file, search first to "
        f"satisfy the gate, then Read + Edit normally."
    )
    print(msg, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
