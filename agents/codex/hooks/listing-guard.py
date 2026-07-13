#!/usr/bin/env python3
"""Codex PreToolUse hook: replace recursive directory listings with lean-ls."""
from __future__ import annotations

import re
import shlex
import sys
from pathlib import Path

from _codex_runtime import bootstrap, load_json_stdin, print_result


REPO = bootstrap()
TOOLS = REPO / ".less_tokens" / "tools"
if not TOOLS.exists():
    TOOLS = REPO / ".claude" / "tools"

from listing_guard import check_listing_guard, is_bare_listing, run_lean_ls  # noqa: E402


def _codex_bash_replacement(command: str) -> str | None:
    stripped = command.strip()
    if not stripped:
        return None

    if re.fullmatch(r"find(?:\s+\.)?(?:\s+-print)?", stripped):
        return (
            "[codex-bash-guard] Broad find blocked.\n"
            "Use: `rg --files`"
        )

    if re.fullmatch(r"git\s+diff(?:\s+--)?", stripped):
        return (
            "[codex-bash-guard] Broad git diff blocked.\n"
            "Use: `git diff --stat` or `git diff --name-only`; then inspect targeted files."
        )

    if re.search(r"(?:^|[;&|])\s*pytest\b", stripped) and re.search(r"\s-(?:v|vv)\b|\s--verbose\b", stripped):
        return (
            "[codex-bash-guard] Verbose pytest run blocked.\n"
            "Use: `pytest -q`; lean-output will summarize failures."
        )

    try:
        parts = shlex.split(stripped)
    except ValueError:
        return None
    if parts and parts[0] == "cat" and len(parts) >= 2 and all(not p.startswith("-") for p in parts[1:]):
        target = parts[1]
        return (
            "[codex-bash-guard] Broad cat blocked.\n"
            f"Use: `sed -n '1,160p' {shlex.quote(target)}` or search before reading."
        )

    return None


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
    payload = load_json_stdin()
    if not payload:
        return 0
    if payload.get("tool_name") != "Bash":
        return 0
    cmd = (payload.get("tool_input") or {}).get("command", "")
    replacement = _codex_bash_replacement(cmd)
    if replacement:
        print(replacement)
        return 2
    code, stdout, stderr = check_listing_guard(
        cmd,
        enabled=_enabled(),
        python=_python(),
        lean_ls=TOOLS / "lean-ls.py",
        tip_prefix=".less_tokens/tools",
    )
    return print_result(code, stdout, stderr)


if __name__ == "__main__":
    sys.exit(main())
