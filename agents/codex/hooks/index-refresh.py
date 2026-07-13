#!/usr/bin/env python3
"""Codex PostToolUse hook: re-embed indexed files after apply_patch/Edit/Write."""
from __future__ import annotations

import sys

from _codex_runtime import bootstrap, load_json_stdin, print_result

REPO = bootstrap()

from payload import normalize_codex  # noqa: E402
from index_refresh import check_index_refresh  # noqa: E402

try:
    from search_config import (  # noqa: E402
        active_state_dir,
        EXCLUDED_DIR_NAMES,
        EXCLUDED_DIR_PREFIXES,
        INDEXED_ROOT_GLOBS,
        INDEXED_SOURCE_DIRS,
        VENV_PY,
    )
    config = {
        "venv_py": REPO / ".less_tokens" / "bin" / "python",
        "excluded_prefixes": EXCLUDED_DIR_PREFIXES,
        "excluded_names": EXCLUDED_DIR_NAMES,
        "dirs": INDEXED_SOURCE_DIRS,
        "root_globs": INDEXED_ROOT_GLOBS,
        "tool_prefix": ".less_tokens/tools",
    }
    state_dir = active_state_dir()
except Exception:
    config = {}
    state_dir = REPO / ".less_tokens" / "state"

def main() -> int:
    raw = load_json_stdin()
    if not raw:
        return 0
    payload = normalize_codex(raw)
    code, stdout, stderr = check_index_refresh(payload, repo=REPO, state_dir=state_dir, config=config)
    return print_result(code, stdout, stderr)


if __name__ == "__main__":
    sys.exit(main())
