#!/usr/bin/env python3
"""Codex PreToolUse hook: block large whole-file reads before locating target."""
from __future__ import annotations

import sys

from _codex_runtime import bootstrap, load_json_stdin, map_bash_read, map_read, print_pre_tool_result

REPO = bootstrap()

from payload import normalize_codex  # noqa: E402
from grep_first_read import check_grep_first_read  # noqa: E402

try:
    from search_config import (  # noqa: E402
        EXCLUDED_DIR_NAMES,
        EXCLUDED_DIR_PREFIXES,
        GREP_FIRST_LINE_THRESHOLD,
        INDEXED_ROOT_GLOBS,
        INDEXED_SOURCE_DIRS,
        WINDOW_SECONDS,
        active_state_dir,
    )
    state_dir = active_state_dir()
    config = {
        "excluded_prefixes": EXCLUDED_DIR_PREFIXES,
        "excluded_names": EXCLUDED_DIR_NAMES,
        "dirs": INDEXED_SOURCE_DIRS,
        "root_globs": INDEXED_ROOT_GLOBS,
        "window_seconds": WINDOW_SECONDS,
        "line_threshold": GREP_FIRST_LINE_THRESHOLD,
        "venv_py": ".less_tokens/bin/python",
        "tool_prefix": ".less_tokens/tools",
        "read_example": "Read file_path={file_path!r} offset={start} limit={limit}",
    }
except Exception:
    state_dir = REPO / ".less_tokens" / "state"
    config = {"line_threshold": 150, "window_seconds": 300}


def main() -> int:
    raw = load_json_stdin(map_read, map_bash_read)
    if not raw:
        return 0
    payload = normalize_codex(raw)
    code, stdout, stderr = check_grep_first_read(payload, repo=REPO, state_dir=state_dir, config=config)
    return print_pre_tool_result(code, stdout, stderr)


if __name__ == "__main__":
    sys.exit(main())
