#!/usr/bin/env python3
"""Codex PreToolUse hook: block reads of stale continue.md handoffs."""
from __future__ import annotations

import sys

from _codex_runtime import bootstrap, load_json_stdin, map_read, print_result

REPO = bootstrap()

from continue_freshness import check_continue_freshness  # noqa: E402


def main() -> int:
    raw = load_json_stdin(map_read)
    if raw.get("tool_name") != "Read":
        return 0
    file_path = (raw.get("tool_input") or {}).get("file_path", "")
    if not file_path:
        return 0
    return print_result(*check_continue_freshness(file_path, repo=REPO))


if __name__ == "__main__":
    sys.exit(main())
