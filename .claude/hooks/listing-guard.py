#!/usr/bin/env python3
"""PreToolUse hook: intercept bare directory-listing Bash commands.

Detects and redirects:
  - ls -R / ls --recursive          (always a dump)
  - tree without -L, or -L > 3      (full tree dump)
  - find <path> without -name/-iname/-path/-newer/-mtime filter

Exits 2 with lean-ls output — Claude sees the compact listing instead of
a raw recursive dump. Set LISTING_GUARD_ENABLED=False in search_config.py
to disable. install.py wires this as PreToolUse on Bash.
"""
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
LEAN_LS = REPO / ".claude" / "tools" / "lean-ls.py"


def _load_enabled() -> bool:
    try:
        sys.path.insert(0, str(REPO / ".claude" / "tools"))
        from search_config import LISTING_GUARD_ENABLED  # noqa: PLC0415
        return bool(LISTING_GUARD_ENABLED)
    except Exception:
        return True  # default on


def _extract_path_after(cmd: str, keyword: str) -> str:
    """First non-flag token after keyword, or '.'."""
    rest = cmd[cmd.index(keyword) + len(keyword):].strip()
    for tok in rest.split():
        if not tok.startswith("-"):
            return tok
    return "."


def _unquote(cmd: str) -> str:
    """Remove contents of quoted strings (best-effort) before pattern matching."""
    cmd = re.sub(r'"[^"]*"', '""', cmd)
    cmd = re.sub(r"'[^']*'", "''", cmd)
    return cmd


def is_bare_listing(cmd: str) -> tuple[bool, str]:
    """Return (should_intercept, target_path)."""
    stripped = cmd.strip()
    unquoted = _unquote(stripped)

    # ls -R / ls --recursive
    if re.search(r'\bls\b', unquoted) and (
        re.search(r'-[a-zA-Z]*R\b', unquoted)
        or re.search(r'--recursive\b', unquoted)
    ):
        tokens = stripped.split()
        path = "."
        for tok in reversed(tokens[1:]):
            if not tok.startswith("-"):
                path = tok
                break
        return True, path

    # tree — intercept if no -L flag, or -L > 3
    # Match tree as a command: at start or after shell operators (&& ; | &)
    if re.search(r'(?:^|[;&|])\s*tree\b', unquoted):
        m = re.search(r'-L\s+(\d+)', unquoted)
        if not m or int(m.group(1)) > 3:
            tokens = stripped.split()
            path = "."
            for tok in tokens[1:]:
                if not tok.startswith("-"):
                    path = tok
                    break
            return True, path

    # find <path> — intercept if no meaningful filter
    if re.search(r'(?:^|[;&|])\s*find\b', unquoted):
        # Allow through if any selective predicate is present
        _ALLOW_RE = re.compile(
            r'-(name|iname|path|newer|mtime|ctime|atime|exec|regex|wholename|size)\b'
            r'|(-maxdepth\s+[0-2]\b)'
        )
        if not _ALLOW_RE.search(unquoted):
            path = _extract_path_after(stripped, "find")
            return True, path

    return False, "."


def _run_lean_ls(path: str) -> str:
    result = subprocess.run(
        [sys.executable, str(LEAN_LS), path],
        capture_output=True, text=True,
    )
    out = result.stdout.strip()
    if result.returncode != 0 or not out:
        return f"[lean-ls error: {result.stderr.strip() or 'no output'}]"
    return out


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    if payload.get("tool_name") != "Bash":
        return 0

    cmd = payload.get("tool_input", {}).get("command", "")
    if not cmd:
        return 0

    if not _load_enabled():
        return 0

    should_intercept, path = is_bare_listing(cmd)
    if not should_intercept:
        return 0

    listing = _run_lean_ls(path)
    print(
        f"[listing-guard] Replaced bare listing with lean-ls "
        f"(depth-limited, .gitignore-aware):\n\n"
        f"{listing}\n\n"
        f"Tip: `.claude/tools/lean-ls.py {path} --depth N` to adjust depth."
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
