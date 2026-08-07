#!/usr/bin/env python3
"""PreToolUse hook: block whole-file Reads of high-noise files."""

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
    from agents.common.hooks.read_guard import check_read_guard  # type: ignore[import]
except Exception:
    from read_guard import check_read_guard  # type: ignore[no-redef]

try:
    from search_config import (
        READ_DENY_DATA_EXTS,
        READ_DENY_DATA_MAX_LINES,
        READ_DENY_GLOBS,
    )  # noqa: E402
except Exception:
    READ_DENY_GLOBS = ()
    READ_DENY_DATA_MAX_LINES = 1000
    READ_DENY_DATA_EXTS = (".csv", ".tsv", ".json", ".jsonl", ".ndjson", ".parquet")


def check(file_path: str) -> str | None:
    return check_read_guard(
        file_path,
        offset=None,
        deny_globs=READ_DENY_GLOBS,
        data_max_lines=READ_DENY_DATA_MAX_LINES,
        data_exts=READ_DENY_DATA_EXTS,
    )


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if payload.get("tool_name") != "Read":
        return 0
    inp = payload.get("tool_input", {}) or {}
    if inp.get("offset") is not None:
        return 0
    reason = check(inp.get("file_path", ""))
    if reason:
        print("Read-guard: " + reason, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
