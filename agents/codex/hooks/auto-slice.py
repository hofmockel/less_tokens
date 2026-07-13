#!/usr/bin/env python3
"""Codex PreToolUse hook: redirect whole-file reads to last-search slices."""
from __future__ import annotations

import sys

from _codex_runtime import bootstrap, load_json_stdin, map_read, print_result

REPO = bootstrap()

from payload import normalize_codex  # noqa: E402
from auto_slice import check_auto_slice  # noqa: E402

try:
    from search_config import WINDOW_SECONDS, active_state_dir  # noqa: E402
    state_dir = active_state_dir()
except Exception:
    WINDOW_SECONDS = 300
    state_dir = REPO / ".less_tokens" / "state"


def main() -> int:
    raw = load_json_stdin(map_read)
    if not raw:
        return 0
    payload = normalize_codex(raw)
    code, stdout, stderr = check_auto_slice(
        payload,
        state_dir=state_dir,
        window_seconds=WINDOW_SECONDS,
        read_example="Read file_path={file_path!r} offset={start} limit={limit}",
    )
    return print_result(code, stdout, stderr)


if __name__ == "__main__":
    sys.exit(main())
