#!/usr/bin/env python3
"""Codex PreToolUse hook: block whole-file reads of noisy files."""
from __future__ import annotations

import sys

from _codex_runtime import bootstrap, FILESYSTEM_READ_TOOLS, load_json_stdin, map_bash_read, print_pre_tool_result

bootstrap()

from read_guard import check_read_guard  # noqa: E402

try:
    from search_config import READ_DENY_DATA_EXTS, READ_DENY_DATA_MAX_LINES, READ_DENY_GLOBS  # noqa: E402
except Exception:
    READ_DENY_GLOBS = ()
    READ_DENY_DATA_MAX_LINES = 1000
    READ_DENY_DATA_EXTS = (".csv", ".tsv", ".json", ".jsonl", ".ndjson", ".parquet")


def _file_input(raw: dict) -> tuple[str, object]:
    inp = raw.get("tool_input") or {}
    if raw.get("tool_name") in FILESYSTEM_READ_TOOLS:
        return str(inp.get("path", "")), inp.get("offset")
    return str(inp.get("file_path") or inp.get("path") or ""), inp.get("offset")


def main() -> int:
    raw = load_json_stdin(map_bash_read)
    if not raw:
        return 0
    if raw.get("tool_name") not in {"Read", *FILESYSTEM_READ_TOOLS}:
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
        return print_pre_tool_result(2, "", "Read-guard: " + reason)
    return 0


if __name__ == "__main__":
    sys.exit(main())
