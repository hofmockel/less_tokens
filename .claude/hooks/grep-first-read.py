#!/usr/bin/env python3
"""PreToolUse hook: block whole-file Reads of large files."""
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
    from agents.common.hooks.grep_first_read import check_grep_first_read  # type: ignore[import]
    from agents.common.hooks.payload import normalize_claude
    from agents.common.hooks.search_first import is_indexed as _common_is_indexed, search_was_recent as _common_recent
except Exception:
    from grep_first_read import check_grep_first_read  # type: ignore[no-redef]
    from payload import normalize_claude  # type: ignore[no-redef]
    from search_first import is_indexed as _common_is_indexed, search_was_recent as _common_recent  # type: ignore[no-redef]

try:
    from search_config import (  # noqa: E402
        active_state_dir,
        EXCLUDED_DIR_NAMES,
        EXCLUDED_DIR_PREFIXES,
        GREP_FIRST_LINE_THRESHOLD,
        INDEXED_ROOT_GLOBS,
        INDEXED_SOURCE_DIRS,
        VENV_PY,
        WINDOW_SECONDS,
    )
except Exception:
    GREP_FIRST_LINE_THRESHOLD = 150
    EXCLUDED_DIR_NAMES = set()
    EXCLUDED_DIR_PREFIXES = ()
    INDEXED_ROOT_GLOBS = ("*.md",)
    INDEXED_SOURCE_DIRS = ()
    VENV_PY = REPO / ".claude" / ".venv-tokens" / "bin" / "python"
    WINDOW_SECONDS = 300

    def active_state_dir() -> Path:  # type: ignore[misc]
        return REPO / ".claude" / "state"

RANGES_FILE = active_state_dir() / "last-search.json"


def _is_indexed(p: Path) -> bool:
    return _common_is_indexed(
        p,
        REPO,
        excluded_prefixes=EXCLUDED_DIR_PREFIXES,
        excluded_names=set(EXCLUDED_DIR_NAMES),
        indexed_dirs=INDEXED_SOURCE_DIRS,
        root_globs=INDEXED_ROOT_GLOBS,
    )


def _search_was_recent() -> bool:
    return _common_recent(active_state_dir(), WINDOW_SECONDS)


def check(file_path: str, offset: object) -> str | None:
    payload = normalize_claude({"tool_name": "Read", "tool_input": {"file_path": file_path, "offset": offset}})
    config = {
        "excluded_prefixes": EXCLUDED_DIR_PREFIXES,
        "excluded_names": EXCLUDED_DIR_NAMES,
        "dirs": INDEXED_SOURCE_DIRS,
        "root_globs": INDEXED_ROOT_GLOBS,
        "window_seconds": WINDOW_SECONDS,
        "line_threshold": GREP_FIRST_LINE_THRESHOLD,
        "venv_py": str(VENV_PY),
        "tool_prefix": ".claude/tools",
        "read_example": "Read(file_path={file_path!r}, offset={start}, limit={limit})",
        "ranges_file": RANGES_FILE,
        "is_indexed": _is_indexed,
        "search_was_recent": _search_was_recent,
    }
    code, _, stderr = check_grep_first_read(payload, repo=REPO, state_dir=active_state_dir(), config=config)
    return stderr.replace("Grep-first gate:", "Grep-first gate (S13):") if code == 2 else None


def main() -> int:
    try:
        raw = json.load(sys.stdin)
    except Exception:
        return 0
    if raw.get("tool_name") != "Read":
        return 0
    inp = raw.get("tool_input", {}) or {}
    reason = check(inp.get("file_path", ""), inp.get("offset"))
    if reason:
        print("Grep-first: " + reason, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
