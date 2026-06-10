#!/usr/bin/env python3
"""PostToolUse hook: emit compact diff after Edit/Write; record path for re-Read guard.

For Edit: diff is computed from old_string/new_string in tool_input (no I/O).
For Write: diff is computed via `git diff HEAD -- <file>`; falls back to a
  line-count summary when git is unavailable or the file is untracked.

Outputs a hookSpecificOutput JSON to stdout so Claude sees the change without
re-reading the file.  Also writes STATE_DIR/last-edit.json so the
read-after-edit PreToolUse hook can block a verify re-Read of the same file.

install.py wires this as PostToolUse on Edit|Write alongside index-refresh.py.
"""
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
sys.path.insert(0, str(REPO / ".claude" / "tools"))

try:
    from search_config import MAX_DIFF_LINES, active_state_dir as _active_state_dir
except Exception:
    MAX_DIFF_LINES = 60
    def _active_state_dir() -> Path:  # type: ignore[misc]
        return REPO / ".claude" / "state"
_CONTEXT = 2  # unified diff context lines


def _diff_edit(old: str, new: str, label: str) -> list[str]:
    """Compute unified diff lines from Edit old_string/new_string."""
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    # Ensure trailing newline so diff doesn't show \\ No newline at end
    if old_lines and not old_lines[-1].endswith("\n"):
        old_lines[-1] += "\n"
    if new_lines and not new_lines[-1].endswith("\n"):
        new_lines[-1] += "\n"
    return list(difflib.unified_diff(
        old_lines, new_lines,
        fromfile=f"a/{label}", tofile=f"b/{label}",
        n=_CONTEXT,
    ))


def _diff_write(file_path: str) -> list[str]:
    """Compute diff for a Write via git diff HEAD; fallback to line count."""
    p = Path(file_path)
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD", "--", file_path],
            capture_output=True, text=True, timeout=5, cwd=REPO,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.splitlines(keepends=True)
        # Untracked or new file — show as +lines
        if p.exists():
            lines = p.read_text(errors="replace").splitlines(keepends=True)
            added = [f"+{l}" for l in lines]
            header = [
                f"--- /dev/null\n",
                f"+++ b/{p.name}\n",
                f"@@ -0,0 +1,{len(lines)} @@\n",
            ]
            return header + added
    except Exception:
        pass
    # Last resort: file size note
    try:
        n = sum(1 for _ in p.open())
        return [f"# Write: {p.name} — {n} lines written\n"]
    except Exception:
        return [f"# Write: {p.name}\n"]


def _cap(diff_lines: list[str], max_lines: int) -> str:
    """Cap diff at max_lines; append a summary tail if truncated."""
    if max_lines <= 0 or len(diff_lines) <= max_lines:
        return "".join(diff_lines)
    head = "".join(diff_lines[:max_lines])
    remaining = len(diff_lines) - max_lines
    return head + f"\n... +{remaining} more diff lines (truncated) ...\n"


def _record_edit(file_path: str) -> None:
    """Append/update path→timestamp in last-edit.json."""
    try:
        sd = _active_state_dir()
        last_edit_file = sd / "last-edit.json"
        sd.mkdir(parents=True, exist_ok=True)
        try:
            data: dict = json.loads(last_edit_file.read_text())
        except Exception:
            data = {}
        data[str(Path(file_path).resolve())] = time.time()
        last_edit_file.write_text(json.dumps(data))
    except Exception:
        pass


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    tool_name = payload.get("tool_name", "")
    if tool_name not in ("Edit", "Write"):
        return 0

    inp = payload.get("tool_input", {})
    file_path = inp.get("file_path", "")
    if not file_path:
        return 0

    label = Path(file_path).name

    if tool_name == "Edit":
        old = inp.get("old_string", "")
        new = inp.get("new_string", "")
        if not old and not new:
            return 0
        diff_lines = _diff_edit(old, new, label)
    else:
        diff_lines = _diff_write(file_path)

    if not diff_lines:
        return 0

    _record_edit(file_path)

    diff_text = _cap(diff_lines, MAX_DIFF_LINES)
    context = (
        f"post-edit-diff ({label}):\n"
        f"```diff\n{diff_text}```\n"
        f"Diff in context — skip re-Read of {label} unless you need lines outside this change."
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
