#!/usr/bin/env python3
"""PostToolUse hook: emit compact diff after Edit/Write; record path."""
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
    from agents.common.hooks.post_edit_diff import cap as _cap_common, check_post_edit_diff, diff_edit, diff_write, record_edit
except Exception:
    from payload import normalize_claude  # type: ignore[no-redef]
    from post_edit_diff import cap as _cap_common, check_post_edit_diff, diff_edit, diff_write, record_edit  # type: ignore[no-redef]

try:
    from search_config import MAX_DIFF_LINES, active_state_dir as _active_state_dir  # noqa: E402
except Exception:
    MAX_DIFF_LINES = 60

    def _active_state_dir() -> Path:  # type: ignore[misc]
        return REPO / ".claude" / "state"


def _diff_edit(old: str, new: str, label: str) -> list[str]:
    return diff_edit(old, new, label)


def _diff_write(file_path: str) -> list[str]:
    return diff_write(file_path, repo=REPO)


def _cap(diff_lines: list[str], max_lines: int) -> str:
    return _cap_common(diff_lines, max_lines)


def _record_edit(file_path: str) -> None:
    record_edit(_active_state_dir(), file_path)


def main() -> int:
    try:
        raw = json.load(sys.stdin)
    except Exception:
        return 0
    code, stdout, stderr = check_post_edit_diff(
        normalize_claude(raw),
        repo=REPO,
        state_dir=_active_state_dir(),
        max_diff_lines=MAX_DIFF_LINES,
        include_apply_patch=False,
        message="Diff in context — skip re-Read of {label} unless you need lines outside this change.",
    )
    if stdout:
        print(stdout)
    if stderr:
        print(stderr, file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
