#!/usr/bin/env python3
"""PreToolUse hook: block reads of a stale continue.md until drift is surfaced."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _resolve_repo() -> Path:
    if os.environ.get("LESS_TOKENS_REPO"):
        return Path(os.environ["LESS_TOKENS_REPO"]).resolve()
    curr = Path(__file__).resolve().parent
    for _ in range(4):
        if (curr / "CLAUDE.md").exists() or (curr / ".git").exists():
            return curr
        curr = curr.parent
    curr = Path.cwd().resolve()
    for _ in range(10):
        if (curr / ".git").exists() or (curr / "CLAUDE.md").exists():
            return curr
        if curr == curr.parent:
            break
        curr = curr.parent
    return Path(__file__).resolve().parent.parent.parent


REPO = _resolve_repo()
sys.path[:0] = [
    str(REPO),
    str(REPO / "agents" / "common" / "hooks"),
    str(REPO / ".claude" / "hooks" / "common"),
]

try:
    from agents.common.hooks.continue_freshness import check_continue_freshness  # type: ignore[import]
except Exception:
    from continue_freshness import check_continue_freshness  # type: ignore[no-redef]


def main() -> int:
    try:
        raw = json.load(sys.stdin)
    except Exception:
        return 0
    if raw.get("tool_name") != "Read":
        return 0
    inp = raw.get("tool_input", {}) or {}
    file_path = inp.get("file_path", "")
    if not file_path:
        return 0
    code, _, stderr = check_continue_freshness(file_path, repo=REPO)
    if code == 2:
        print("Continue-freshness: " + stderr, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
