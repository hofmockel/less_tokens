#!/usr/bin/env python3
"""Codex PreToolUse hook: block whole-file rereads soon after an edit."""
from __future__ import annotations

import sys

from _codex_runtime import bootstrap, load_json_stdin, map_bash_read, map_read, print_result

REPO = bootstrap()

from payload import normalize_codex  # noqa: E402
from read_after_edit import check_read_after_edit  # noqa: E402

try:
    from search_config import LAST_EDIT_WINDOW_SECONDS, active_state_dir  # noqa: E402
    state_dir = active_state_dir()
except Exception:
    LAST_EDIT_WINDOW_SECONDS = 120
    state_dir = REPO / ".less_tokens" / "state"


def main() -> int:
    raw = load_json_stdin(map_read, map_bash_read)
    if not raw:
        return 0
    payload = normalize_codex(raw)
    code, stdout, stderr = check_read_after_edit(
        payload,
        state_dir=state_dir,
        window_seconds=LAST_EDIT_WINDOW_SECONDS,
    )
    return print_result(code, stdout, stderr)


if __name__ == "__main__":
    sys.exit(main())
