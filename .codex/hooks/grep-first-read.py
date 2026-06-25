#!/usr/bin/env python3
"""Codex PreToolUse hook: block large whole-file reads before locating target."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _resolve_repo() -> Path:
    if os.environ.get("LESS_TOKENS_REPO"):
        return Path(os.environ["LESS_TOKENS_REPO"]).resolve()
    curr = Path(__file__).resolve().parent
    for _ in range(6):
        if (curr / ".git").exists() or (curr / "AGENTS.md").exists():
            return curr
        curr = curr.parent
    return Path(__file__).resolve().parent.parent.parent.parent


REPO = _resolve_repo()
sys.path.insert(0, str(REPO / ".less_tokens" / "hooks"))
sys.path.insert(0, str(REPO / "agents" / "common" / "hooks"))
sys.path.insert(0, str(REPO / ".less_tokens" / "tools"))
sys.path.insert(0, str(REPO / ".claude" / "tools"))

from payload import normalize_codex  # noqa: E402
from grep_first_read import check_grep_first_read  # noqa: E402

try:
    from search_config import (  # noqa: E402
        EXCLUDED_DIR_NAMES,
        EXCLUDED_DIR_PREFIXES,
        GREP_FIRST_LINE_THRESHOLD,
        INDEXED_ROOT_GLOBS,
        INDEXED_SOURCE_DIRS,
        WINDOW_SECONDS,
        active_state_dir,
    )
    state_dir = active_state_dir()
    config = {
        "excluded_prefixes": EXCLUDED_DIR_PREFIXES,
        "excluded_names": EXCLUDED_DIR_NAMES,
        "dirs": INDEXED_SOURCE_DIRS,
        "root_globs": INDEXED_ROOT_GLOBS,
        "window_seconds": WINDOW_SECONDS,
        "line_threshold": GREP_FIRST_LINE_THRESHOLD,
        "venv_py": ".less_tokens/bin/python",
        "tool_prefix": ".less_tokens/tools",
        "read_example": "Read file_path={file_path!r} offset={start} limit={limit}",
    }
except Exception:
    state_dir = REPO / ".less_tokens" / "state"
    config = {"line_threshold": 150, "window_seconds": 300}


def _map_read(raw: dict) -> dict:
    if raw.get("tool_name") == "mcp__filesystem__read_file":
        inp = raw.setdefault("tool_input", {})
        raw["tool_name"] = "Read"
        inp["file_path"] = inp.get("path", "")
    return raw


def main() -> int:
    try:
        raw = _map_read(json.loads(sys.stdin.read()))
    except Exception:
        return 0
    payload = normalize_codex(raw)
    code, stdout, stderr = check_grep_first_read(payload, repo=REPO, state_dir=state_dir, config=config)
    if stdout:
        print(stdout)
    if stderr:
        print(stderr, file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
