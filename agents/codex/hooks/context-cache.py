#!/usr/bin/env python3
"""Codex PreToolUse hook: block repeated reads/searches already in context."""
from __future__ import annotations

import sys
from pathlib import Path

from _codex_runtime import bootstrap, load_json_stdin, map_read_or_search, print_pre_tool_result

REPO = bootstrap()

from context_cache import check_context_cache  # noqa: E402
from payload import normalize_codex  # noqa: E402

try:
    from search_config import CONTEXT_CACHE_BASH_TTL, CONTEXT_CACHE_ENABLED, CONTEXT_CACHE_GREP_TTL, active_state_dir  # noqa: E402
except Exception:
    CONTEXT_CACHE_BASH_TTL = 120
    CONTEXT_CACHE_ENABLED = True
    CONTEXT_CACHE_GREP_TTL = 300

    def active_state_dir() -> Path:  # type: ignore[misc]
        return REPO / ".less_tokens" / "state"


def main() -> int:
    raw = load_json_stdin(map_read_or_search)
    if not raw:
        return 0
    code, stdout, stderr = check_context_cache(
        normalize_codex(raw),
        state_dir=active_state_dir(),
        enabled=CONTEXT_CACHE_ENABLED,
        grep_ttl=CONTEXT_CACHE_GREP_TTL,
        bash_ttl=CONTEXT_CACHE_BASH_TTL,
        event_name=str(raw.get("hook_event_name") or raw.get("hookEventName") or "PreToolUse"),
    )
    return print_pre_tool_result(code, stdout, stderr)


if __name__ == "__main__":
    sys.exit(main())
