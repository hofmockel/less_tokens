#!/usr/bin/env python3
"""Codex PreToolUse hook: replace recursive directory listings with lean-ls."""
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
]
TOOLS = REPO / ".less_tokens" / "tools"
if not TOOLS.exists():
    TOOLS = REPO / ".claude" / "tools"
sys.path.append(str(TOOLS))

from listing_guard import check_listing_guard, is_bare_listing, run_lean_ls  # noqa: E402


def _enabled() -> bool:
    try:
        from search_config import LISTING_GUARD_ENABLED  # noqa: PLC0415
        return bool(LISTING_GUARD_ENABLED)
    except Exception:
        return True


def _python() -> Path:
    p = REPO / ".less_tokens" / "bin" / "python"
    return p if p.exists() else Path(sys.executable)


def _run_lean_ls(path: str) -> str:
    return run_lean_ls(path, python=_python(), lean_ls=TOOLS / "lean-ls.py")


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read())
    except Exception:
        return 0
    if payload.get("tool_name") != "Bash":
        return 0
    cmd = (payload.get("tool_input") or {}).get("command", "")
    code, stdout, stderr = check_listing_guard(
        cmd,
        enabled=_enabled(),
        python=_python(),
        lean_ls=TOOLS / "lean-ls.py",
        tip_prefix=".less_tokens/tools",
    )
    if stdout:
        print(stdout)
    if stderr:
        print(stderr, file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
