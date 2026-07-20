#!/usr/bin/env python3
"""Codex PreToolUse hook: redirect whole-file reads to last-search slices."""
from __future__ import annotations

import sys

from _codex_runtime import (
    bash_slice_updated_input,
    bootstrap,
    load_json_stdin,
    map_bash_read,
    map_read,
    pre_tool_allow,
    print_pre_tool_result,
)

REPO = bootstrap()

from payload import normalize_codex  # noqa: E402
from auto_slice import check_auto_slice, ranges_for  # noqa: E402

try:
    from search_config import WINDOW_SECONDS, active_state_dir  # noqa: E402
    state_dir = active_state_dir()
except Exception:
    WINDOW_SECONDS = 300
    state_dir = REPO / ".less_tokens" / "state"


def main() -> int:
    raw = load_json_stdin()
    if not raw:
        return 0
    original_tool = raw.get("tool_name")
    original_input = dict(raw.get("tool_input") or {})
    raw = map_bash_read(map_read(raw))
    payload = normalize_codex(raw)
    code, stdout, stderr = check_auto_slice(
        payload,
        state_dir=state_dir,
        window_seconds=WINDOW_SECONDS,
        read_example="Read file_path={file_path!r} offset={start} limit={limit}",
    )
    if code == 2:
        inp = payload.tool_input or {}
        spans = ranges_for(
            inp.get("file_path", ""),
            ranges_file=state_dir / "last-search.json",
            window_seconds=WINDOW_SECONDS,
        )
        if spans:
            start, end = spans[0]
            updated = bash_slice_updated_input(
                original_tool,
                original_input,
                start=start,
                limit=max(1, end - start + 1),
            )
            if updated is not None:
                print(pre_tool_allow(updated))
                return 0
    return print_pre_tool_result(code, stdout, stderr)


if __name__ == "__main__":
    sys.exit(main())
