#!/usr/bin/env python3
"""Codex PreToolUse hook: replace recursive directory listings with lean-ls."""
from __future__ import annotations

import json
import os
import re
import subprocess
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
TOOLS = REPO / ".less_tokens" / "tools"
if not TOOLS.exists():
    TOOLS = REPO / ".claude" / "tools"


def _enabled() -> bool:
    try:
        sys.path.insert(0, str(TOOLS))
        from search_config import LISTING_GUARD_ENABLED  # noqa: PLC0415
        return bool(LISTING_GUARD_ENABLED)
    except Exception:
        return True


def _unquote(cmd: str) -> str:
    cmd = re.sub(r'"[^"]*"', '""', cmd)
    return re.sub(r"'[^']*'", "''", cmd)


def _extract_path_after(cmd: str, keyword: str) -> str:
    rest = cmd[cmd.index(keyword) + len(keyword):].strip()
    for tok in rest.split():
        if not tok.startswith("-"):
            return tok
    return "."


def is_bare_listing(cmd: str) -> tuple[bool, str]:
    stripped = cmd.strip()
    unquoted = _unquote(stripped)
    if re.search(r"\bls\b", unquoted) and (
        re.search(r"-[a-zA-Z]*R\b", unquoted) or re.search(r"--recursive\b", unquoted)
    ):
        tokens = stripped.split()
        path = "."
        for tok in reversed(tokens[1:]):
            if not tok.startswith("-"):
                path = tok
                break
        return True, path
    if re.search(r"(?:^|[;&|])\s*tree\b", unquoted):
        m = re.search(r"-L\s+(\d+)", unquoted)
        if not m or int(m.group(1)) > 3:
            tokens = stripped.split()
            path = "."
            for tok in tokens[1:]:
                if not tok.startswith("-"):
                    path = tok
                    break
            return True, path
    if re.search(r"(?:^|[;&|])\s*find\b", unquoted):
        allow = re.compile(
            r"-(name|iname|path|newer|mtime|ctime|atime|exec|regex|wholename|size|type)\b"
            r"|(-maxdepth\s+[0-2]\b)"
        )
        if not allow.search(unquoted):
            return True, _extract_path_after(stripped, "find")
    return False, "."


def _python() -> Path:
    p = REPO / ".less_tokens" / "bin" / "python"
    return p if p.exists() else Path(sys.executable)


def _run_lean_ls(path: str) -> str:
    lean_ls = TOOLS / "lean-ls.py"
    if not lean_ls.exists():
        return "[lean-ls error: tool missing]"
    result = subprocess.run(
        [str(_python()), str(lean_ls), path],
        capture_output=True,
        text=True,
    )
    out = result.stdout.strip()
    if result.returncode != 0 or not out:
        return f"[lean-ls error: {result.stderr.strip() or 'no output'}]"
    return out


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read())
    except Exception:
        return 0
    if payload.get("tool_name") != "Bash":
        return 0
    cmd = (payload.get("tool_input") or {}).get("command", "")
    if not cmd or not _enabled():
        return 0
    should_intercept, path = is_bare_listing(cmd)
    if not should_intercept:
        return 0
    listing = _run_lean_ls(path)
    print(
        "[listing-guard] Replaced bare listing with lean-ls "
        "(depth-limited, .gitignore-aware):\n\n"
        f"{listing}\n\n"
        f"Tip: `.less_tokens/tools/lean-ls.py {path} --depth N` to adjust depth."
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
