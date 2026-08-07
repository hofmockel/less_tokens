#!/usr/bin/env python3
"""PostToolUse hook: re-embed indexed files after Edit/Write."""

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
    from agents.common.hooks.index_refresh import check_index_refresh  # type: ignore[import]
    from agents.common.hooks.payload import normalize_claude
    from agents.common.hooks.search_first import is_indexed as _common_is_indexed
except Exception:
    from index_refresh import check_index_refresh  # type: ignore[no-redef]
    from payload import normalize_claude  # type: ignore[no-redef]
    from search_first import is_indexed as _common_is_indexed  # type: ignore[no-redef]

try:
    import search_config as _search_config  # noqa: E402
    from search_config import (  # noqa: E402
        active_state_dir as _active_state_dir,
        EXCLUDED_DIR_NAMES,
        EXCLUDED_DIR_PREFIXES,
        INDEXED_ROOT_GLOBS,
        INDEXED_SOURCE_DIRS as INDEXED_DIRS,
        VENV_PY,
    )

    SEARCH_BACKEND = getattr(_search_config, "SEARCH_BACKEND", "sqlite")
except Exception:
    EXCLUDED_DIR_NAMES: set = set()
    EXCLUDED_DIR_PREFIXES: tuple = ()
    INDEXED_ROOT_GLOBS: tuple = ("*.md",)
    INDEXED_DIRS: tuple = ()
    SEARCH_BACKEND = "sqlite"
    VENV_PY = None  # type: ignore[assignment]

    def _active_state_dir() -> Path:  # type: ignore[misc]
        return REPO / ".claude" / "state"


def is_indexed(path: Path) -> bool:
    return _common_is_indexed(
        path,
        REPO,
        excluded_prefixes=EXCLUDED_DIR_PREFIXES,
        excluded_names=set(EXCLUDED_DIR_NAMES),
        indexed_dirs=INDEXED_DIRS,
        root_globs=INDEXED_ROOT_GLOBS,
    )


def main() -> int:
    try:
        raw = json.load(sys.stdin)
    except Exception:
        return 0
    config = {
        "venv_py": VENV_PY,
        "excluded_prefixes": EXCLUDED_DIR_PREFIXES,
        "excluded_names": EXCLUDED_DIR_NAMES,
        "dirs": INDEXED_DIRS,
        "root_globs": INDEXED_ROOT_GLOBS,
        "search_backend": os.environ.get("LESS_TOKENS_SEARCH_BACKEND", SEARCH_BACKEND),
        "tool_prefix": ".claude/tools",
    }
    code, stdout, stderr = check_index_refresh(
        normalize_claude(raw),
        repo=REPO,
        state_dir=_active_state_dir(),
        config=config,
    )
    if stdout:
        print(stdout)
    if stderr:
        print(stderr, file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
