#!/usr/bin/env python3
"""PreToolUse hook: block whole-file Reads of high-noise files.

Lockfiles, minified/generated bundles, notebooks, binaries, and oversized data
files are near-pure token waste. This blocks an un-sliced `Read` of them and
tells Claude to slice or summarize instead. A `Read` with an explicit `offset`
(a deliberate slice) is always allowed, as is anything not on the deny list.

Complements `.claudeignore` (which scopes the project file list but does not
stop an explicit Read). Tune lists in search_config.py; empty globs disable.
install.py wires this as PreToolUse on Read.
"""
from __future__ import annotations

import fnmatch
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
sys.path.insert(0, str(REPO / ".claude" / "tools"))

try:
    from search_config import (
        READ_DENY_DATA_EXTS,
        READ_DENY_DATA_MAX_LINES,
        READ_DENY_GLOBS,
    )
except Exception:
    READ_DENY_GLOBS = ()
    READ_DENY_DATA_MAX_LINES = 1000
    READ_DENY_DATA_EXTS = (".csv", ".tsv", ".json", ".jsonl", ".ndjson", ".parquet")


def _matches_glob(name: str) -> bool:
    return any(fnmatch.fnmatch(name, pat) for pat in READ_DENY_GLOBS)


def _is_binary(p: Path) -> bool:
    try:
        with p.open("rb") as f:
            return b"\x00" in f.read(8192)
    except OSError:
        return False


def _count_lines(p: Path) -> int:
    n = 0
    try:
        with p.open("rb") as f:
            for _ in f:
                n += 1
    except OSError:
        return 0
    return n


def check(file_path: str) -> str | None:
    """Return a block reason, or None to allow."""
    if not file_path:
        return None
    p = Path(file_path)
    name = p.name
    if _matches_glob(name):
        return (f"{name} is a lockfile/generated/binary file (matches READ_DENY_GLOBS) — "
                f"reading it whole is near-pure token waste. If you truly need part of it, "
                f"Read with an explicit offset+limit, or `grep`/`head` the specific lines.")
    if not p.exists():
        return None  # let Read raise its own not-found error
    if _is_binary(p):
        return (f"{name} is binary — Read would dump garbage tokens. "
                f"Use a dedicated tool (or `file`/`xxd | head`) instead.")
    if READ_DENY_DATA_MAX_LINES and p.suffix.lower() in READ_DENY_DATA_EXTS:
        n = _count_lines(p)
        if n > READ_DENY_DATA_MAX_LINES:
            return (f"{name} is a {n:,}-line data file (> {READ_DENY_DATA_MAX_LINES:,}). "
                    f"Don't load it whole — `head`/`wc -l`, a column summary, or Read with "
                    f"offset+limit on the rows you need.")
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if payload.get("tool_name") != "Read":
        return 0
    inp = payload.get("tool_input", {})
    if inp.get("offset"):  # a deliberate slice — allow
        return 0
    reason = check(inp.get("file_path", ""))
    if reason:
        print("Read-guard: " + reason, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
