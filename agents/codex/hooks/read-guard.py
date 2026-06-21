#!/usr/bin/env python3
"""Codex PreToolUse hook: block whole-file reads of noisy files."""
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
sys.path.insert(0, str(REPO / ".less_tokens" / "tools"))
sys.path.insert(0, str(REPO / ".claude" / "tools"))
sys.path.insert(0, str(REPO / ".less_tokens" / "hooks"))
sys.path.insert(0, str(REPO / "agents" / "common" / "hooks"))

from read_guard import check_read_guard  # noqa: E402

try:
    from search_config import READ_DENY_DATA_EXTS, READ_DENY_DATA_MAX_LINES, READ_DENY_GLOBS  # noqa: E402
except Exception:
    READ_DENY_GLOBS = ()
    READ_DENY_DATA_MAX_LINES = 1000
    READ_DENY_DATA_EXTS = (".csv", ".tsv", ".json", ".jsonl", ".ndjson", ".parquet")


def _file_input(raw: dict) -> tuple[str, object]:
    inp = raw.get("tool_input") or {}
    if raw.get("tool_name") == "mcp__filesystem__read_file":
        return str(inp.get("path", "")), inp.get("offset")
    return str(inp.get("file_path") or inp.get("path") or ""), inp.get("offset")


def main() -> int:
    try:
        raw = json.loads(sys.stdin.read())
    except Exception:
        return 0
    if raw.get("tool_name") not in {"Read", "mcp__filesystem__read_file"}:
        return 0
    file_path, offset = _file_input(raw)
    reason = check_read_guard(
        file_path,
        offset=offset,
        deny_globs=READ_DENY_GLOBS,
        data_max_lines=READ_DENY_DATA_MAX_LINES,
        data_exts=READ_DENY_DATA_EXTS,
    )
    if reason:
        print("Read-guard: " + reason, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
