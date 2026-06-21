"""Shared recursive-listing guard logic."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


def _extract_path_after(cmd: str, keyword: str) -> str:
    rest = cmd[cmd.index(keyword) + len(keyword):].strip()
    for tok in rest.split():
        if not tok.startswith("-"):
            return tok
    return "."


def _unquote(cmd: str) -> str:
    cmd = re.sub(r'"[^"]*"', '""', cmd)
    return re.sub(r"'[^']*'", "''", cmd)


def is_bare_listing(cmd: str) -> tuple[bool, str]:
    stripped = cmd.strip()
    unquoted = _unquote(stripped)
    if re.search(r"\bls\b", unquoted) and (
        re.search(r"-[a-zA-Z]*R\b", unquoted) or re.search(r"--recursive\b", unquoted)
    ):
        path = "."
        for tok in reversed(stripped.split()[1:]):
            if not tok.startswith("-"):
                path = tok
                break
        return True, path

    if re.search(r"(?:^|[;&|])\s*tree\b", unquoted):
        m = re.search(r"-L\s+(\d+)", unquoted)
        if not m or int(m.group(1)) > 3:
            path = "."
            for tok in stripped.split()[1:]:
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


def run_lean_ls(path: str, *, python: Path | str, lean_ls: Path) -> str:
    if not lean_ls.exists():
        return "[lean-ls error: tool missing]"
    result = subprocess.run(
        [str(python), str(lean_ls), path],
        capture_output=True,
        text=True,
    )
    out = result.stdout.strip()
    if result.returncode != 0 or not out:
        return f"[lean-ls error: {result.stderr.strip() or 'no output'}]"
    return out


def check_listing_guard(
    command: str,
    *,
    enabled: bool,
    python: Path | str = sys.executable,
    lean_ls: Path,
    tip_prefix: str,
) -> tuple[int, str, str]:
    if not command or not enabled:
        return 0, "", ""
    should_intercept, path = is_bare_listing(command)
    if not should_intercept:
        return 0, "", ""
    listing = run_lean_ls(path, python=python, lean_ls=lean_ls)
    stdout = (
        "[listing-guard] Replaced bare listing with lean-ls "
        "(depth-limited, .gitignore-aware):\n\n"
        f"{listing}\n\n"
        f"Tip: `{tip_prefix}/lean-ls.py {path} --depth N` to adjust depth."
    )
    return 2, stdout, ""
