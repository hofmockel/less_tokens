#!/usr/bin/env python3
"""Codex PostToolUse hook: emit compact diffs and record edited files."""
from __future__ import annotations

import sys
from pathlib import Path

from _codex_runtime import bootstrap, load_json_stdin, print_result

REPO = bootstrap()

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
    payload = load_json_stdin()
    if not payload:
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
    return print_result(code, stdout, stderr)


if __name__ == "__main__":
    sys.exit(main())
