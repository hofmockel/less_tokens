#!/usr/bin/env python3
"""PreToolUse hook: turn whole-file Reads of search hits into slices."""
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
    from agents.common.hooks.auto_slice import check_auto_slice, ranges_for as _ranges_for_common  # type: ignore[import]
    from agents.common.hooks.payload import normalize_claude
except Exception:
    from auto_slice import check_auto_slice, ranges_for as _ranges_for_common  # type: ignore[no-redef]
    from payload import normalize_claude  # type: ignore[no-redef]

try:
    from search_config import active_state_dir, WINDOW_SECONDS  # noqa: E402
except Exception:
    def active_state_dir() -> Path:  # type: ignore[misc]
        return REPO / ".claude" / "state"
    WINDOW_SECONDS = 300

RANGES_FILE = active_state_dir() / "last-search.json"


def _ranges_for(file_path: str) -> list[list[int]]:
    return _ranges_for_common(file_path, ranges_file=RANGES_FILE, window_seconds=WINDOW_SECONDS)


def main() -> int:
    try:
        raw = json.load(sys.stdin)
    except Exception:
        return 0
    code, stdout, stderr = check_auto_slice(
        normalize_claude(raw),
        state_dir=active_state_dir(),
        window_seconds=WINDOW_SECONDS,
        read_example="Read(file_path={file_path!r}, offset={start}, limit={limit})",
    )
    stderr = stderr.replace("Auto-slice:", "Auto-slice (S9):").replace(
        "pass an explicit offset.", "pass offset=1."
    )
    if stdout:
        print(stdout)
    if stderr:
        print(stderr, file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
