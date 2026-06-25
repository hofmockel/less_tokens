#!/usr/bin/env python3
"""Codex PreToolUse hook: block repeated reads/searches already in context."""
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
sys.path[:0] = [
    str(REPO / "agents" / "common" / "hooks"),
    str(REPO / ".less_tokens" / "hooks"),
    str(REPO / ".less_tokens" / "tools"),
    str(REPO / ".claude" / "tools"),
]

from context_cache import check_context_cache  # noqa: E402
from payload import normalize_codex  # noqa: E402

try:
    from search_config import CONTEXT_CACHE_ENABLED, CONTEXT_CACHE_GREP_TTL, active_state_dir  # noqa: E402
except Exception:
    CONTEXT_CACHE_ENABLED = True
    CONTEXT_CACHE_GREP_TTL = 300

    def active_state_dir() -> Path:  # type: ignore[misc]
        return REPO / ".less_tokens" / "state"


def _map_tool(raw: dict) -> dict:
    tool = raw.get("tool_name", "")
    inp = raw.setdefault("tool_input", {})
    if tool == "mcp__filesystem__read_file":
        raw["tool_name"] = "Read"
        inp["file_path"] = inp.get("path", "")
    elif tool.startswith("mcp__filesystem__") and "search" in tool:
        raw["tool_name"] = "Grep"
    return raw


def main() -> int:
    try:
        raw = _map_tool(json.loads(sys.stdin.read()))
    except Exception:
        return 0
    code, stdout, stderr = check_context_cache(
        normalize_codex(raw),
        state_dir=active_state_dir(),
        enabled=CONTEXT_CACHE_ENABLED,
        grep_ttl=CONTEXT_CACHE_GREP_TTL,
    )
    if stdout:
        print(stdout)
    if stderr:
        print(stderr, file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
