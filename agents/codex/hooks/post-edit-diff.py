#!/usr/bin/env python3
"""Codex PostToolUse hook: emit compact diffs and record edited files."""
from __future__ import annotations

import difflib
import json
import os
import subprocess
import sys
import time
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
sys.path.insert(0, str(REPO / ".less_tokens" / "tools"))
sys.path.insert(0, str(REPO / ".claude" / "tools"))

try:
    from search_config import MAX_DIFF_LINES, active_state_dir  # noqa: E402
except Exception:
    MAX_DIFF_LINES = 60

    def active_state_dir() -> Path:  # type: ignore[misc]
        return REPO / ".less_tokens" / "state"


def _diff_edit(old: str, new: str, label: str) -> list[str]:
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    if old_lines and not old_lines[-1].endswith("\n"):
        old_lines[-1] += "\n"
    if new_lines and not new_lines[-1].endswith("\n"):
        new_lines[-1] += "\n"
    return list(difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=f"a/{label}",
        tofile=f"b/{label}",
        n=2,
    ))


def _git_diff(file_path: str) -> list[str]:
    p = Path(file_path)
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD", "--", str(p)],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=REPO,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.splitlines(keepends=True)
    except Exception:
        pass
    return []


def _cap(diff_lines: list[str], max_lines: int) -> str:
    if max_lines <= 0 or len(diff_lines) <= max_lines:
        return "".join(diff_lines)
    return "".join(diff_lines[:max_lines]) + f"\n... +{len(diff_lines) - max_lines} more diff lines (truncated) ...\n"


def _record_edit(file_path: str) -> None:
    try:
        state_dir = active_state_dir()
        state_dir.mkdir(parents=True, exist_ok=True)
        p = state_dir / "last-edit.json"
        try:
            data: dict = json.loads(p.read_text())
        except Exception:
            data = {}
        data[str(Path(file_path).resolve())] = time.time()
        p.write_text(json.dumps(data))
    except Exception:
        pass


def _file_path(raw: dict) -> str:
    inp = raw.get("tool_input") or {}
    return str(inp.get("file_path") or inp.get("path") or "")


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read())
    except Exception:
        return 0
    tool = payload.get("tool_name", "")
    if tool not in {"Edit", "Write", "apply_patch"}:
        return 0
    fp = _file_path(payload)
    if not fp and tool != "apply_patch":
        return 0

    inp = payload.get("tool_input") or {}
    diff_lines: list[str] = []
    label = Path(fp).name if fp else "patch"
    if tool == "Edit":
        old = inp.get("old_string", "")
        new = inp.get("new_string", "")
        if old or new:
            diff_lines = _diff_edit(old, new, label)
    elif fp:
        diff_lines = _git_diff(fp)
    elif tool == "apply_patch":
        diff_lines = _git_diff(".")

    if fp:
        _record_edit(fp)

    if not diff_lines:
        return 0
    diff_text = _cap(diff_lines, MAX_DIFF_LINES)
    context = (
        f"post-edit-diff ({label}):\n"
        f"```diff\n{diff_text}```\n"
        f"Diff in context — skip whole-file rereads unless you need unrelated lines."
    )
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": context,
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
