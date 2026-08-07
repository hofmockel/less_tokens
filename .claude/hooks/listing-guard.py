#!/usr/bin/env python3
"""PreToolUse hook: intercept bare directory-listing Bash commands."""

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
    str(REPO / ".claude" / "tools"),
]

try:
    from agents.common.hooks.listing_guard import (
        check_listing_guard,
        is_bare_listing,
        run_lean_ls,
    )  # type: ignore[import]
except Exception:
    from listing_guard import check_listing_guard, is_bare_listing, run_lean_ls  # type: ignore[no-redef]

LEAN_LS = REPO / ".claude" / "tools" / "lean-ls.py"


def _load_enabled() -> bool:
    try:
        from search_config import LISTING_GUARD_ENABLED  # noqa: PLC0415

        return bool(LISTING_GUARD_ENABLED)
    except Exception:
        return True


def _run_lean_ls(path: str) -> str:
    return run_lean_ls(path, python=sys.executable, lean_ls=LEAN_LS)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if payload.get("tool_name") != "Bash":
        return 0
    cmd = payload.get("tool_input", {}).get("command", "")
    code, stdout, stderr = check_listing_guard(
        cmd,
        enabled=_load_enabled(),
        python=sys.executable,
        lean_ls=LEAN_LS,
        tip_prefix=".claude/tools",
    )
    if stdout:
        print(stdout)
    if stderr:
        print(stderr, file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
