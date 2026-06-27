#!/usr/bin/env python3
"""Codex PostToolUse hook: emit compact diffs and record edited files."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _resolve_repo() -> Path:
    if os.environ.get("LESS_TOKENS_REPO"):
        return Path(os.environ["LESS_TOKENS_REPO"]).resolve()
    curr = Path(__file__).resolve().parent
    for _ in range(6):
        if (curr / ".git").exists() or (curr / "AGENTS.md").exists():
            return curr
        curr = curr.parent
    return Path(__file__).resolve().parent.parent.parent.parent


REPO = _resolve_repo()
sys.path[:0] = [
    str(REPO / "agents" / "common" / "hooks"),
    str(REPO / ".less_tokens" / "hooks"),
    str(REPO / ".less_tokens" / "tools"),
    str(REPO / ".claude" / "tools"),
]

from payload import normalize_codex  # noqa: E402
from post_edit_diff import cap as _cap, check_post_edit_diff, diff_edit as _diff_edit, diff_repo, diff_write, record_edit  # noqa: E402

try:
    from search_config import CODEX_APPLY_PATCH_DIFF_CHARS, MAX_DIFF_LINES, active_state_dir  # noqa: E402
except Exception:
    CODEX_APPLY_PATCH_DIFF_CHARS = 1200
    MAX_DIFF_LINES = 60

    def active_state_dir() -> Path:  # type: ignore[misc]
        return REPO / ".less_tokens" / "state"


def _git_diff(file_path: str) -> list[str]:
    return diff_repo(REPO, file_path) if file_path == "." else diff_write(file_path, repo=REPO)


def _record_edit(file_path: str) -> None:
    record_edit(active_state_dir(), file_path)


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read())
    except Exception:
        return 0
    code, stdout, stderr = check_post_edit_diff(
        normalize_codex(payload),
        repo=REPO,
        state_dir=active_state_dir(),
        max_diff_lines=MAX_DIFF_LINES,
        include_apply_patch=True,
        apply_patch_max_chars=CODEX_APPLY_PATCH_DIFF_CHARS,
        message="Diff in context — skip whole-file rereads unless you need unrelated lines.",
    )
    if stdout:
        print(stdout)
    if stderr:
        print(stderr, file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
