#!/usr/bin/env python3
"""PreToolUse hook: block verify re-Read of recently edited files."""

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
    from agents.common.hooks.payload import normalize_claude  # type: ignore[import]
    from agents.common.hooks.read_after_edit import check_read_after_edit
except Exception:
    from payload import normalize_claude  # type: ignore[no-redef]
    from read_after_edit import check_read_after_edit  # type: ignore[no-redef]

try:
    from search_config import (
        LAST_EDIT_WINDOW_SECONDS,
        active_state_dir as _active_state_dir,
    )  # noqa: E402
except Exception:
    LAST_EDIT_WINDOW_SECONDS = 120

    def _active_state_dir() -> Path:  # type: ignore[misc]
        return REPO / ".claude" / "state"


def _load_edits() -> dict[str, float]:
    try:
        return json.loads((_active_state_dir() / "last-edit.json").read_text())
    except Exception:
        return {}


def main() -> int:
    try:
        raw = json.load(sys.stdin)
    except Exception:
        return 0
    code, stdout, stderr = check_read_after_edit(
        normalize_claude(raw),
        state_dir=_active_state_dir(),
        window_seconds=LAST_EDIT_WINDOW_SECONDS,
    )
    stderr = stderr.replace("whole-file reread", "re-Read").replace(
        "read a targeted slice.", "Read with offset+limit if you need a specific slice."
    )
    if stdout:
        print(stdout)
    if stderr:
        print(stderr, file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
