"""Shared post-edit diff and edit-record logic."""
from __future__ import annotations

import difflib
import json
import subprocess
import time
from pathlib import Path

try:
    from .payload import HookPayload
except ImportError:
    from payload import HookPayload  # type: ignore[no-redef]

_CONTEXT = 2


def diff_edit(old: str, new: str, label: str) -> list[str]:
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
        n=_CONTEXT,
    ))


def diff_write(file_path: str, *, repo: Path | None = None) -> list[str]:
    p = Path(file_path)
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD", "--", p.name],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=p.resolve().parent,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.splitlines(keepends=True)
        if p.exists():
            lines = p.read_text(errors="replace").splitlines(keepends=True)
            return ["--- /dev/null\n", f"+++ b/{p.name}\n", f"@@ -0,0 +1,{len(lines)} @@\n"] + [
                f"+{line}" for line in lines
            ]
    except Exception:
        pass
    try:
        n = sum(1 for _ in p.open())
        return [f"# Write: {p.name} — {n} lines written\n"]
    except Exception:
        return [f"# Write: {p.name}\n"]


def diff_repo(repo: Path, pathspec: str = ".") -> list[str]:
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD", "--", pathspec],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=repo,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.splitlines(keepends=True)
    except Exception:
        pass
    return []


def cap(diff_lines: list[str], max_lines: int) -> str:
    if max_lines <= 0 or len(diff_lines) <= max_lines:
        return "".join(diff_lines)
    return "".join(diff_lines[:max_lines]) + f"\n... +{len(diff_lines) - max_lines} more diff lines (truncated) ...\n"


def record_edit(state_dir: Path, file_path: str) -> None:
    try:
        state_dir.mkdir(parents=True, exist_ok=True)
        last_edit_file = state_dir / "last-edit.json"
        try:
            data: dict = json.loads(last_edit_file.read_text())
        except Exception:
            data = {}
        data[str(Path(file_path).resolve())] = time.time()
        last_edit_file.write_text(json.dumps(data))
    except Exception:
        pass


def hook_context(label: str, diff_text: str, message: str) -> str:
    return f"post-edit-diff ({label}):\n```diff\n{diff_text}```\n{message}"


def check_post_edit_diff(
    payload: HookPayload,
    *,
    repo: Path,
    state_dir: Path,
    max_diff_lines: int,
    include_apply_patch: bool,
    message: str,
) -> tuple[int, str, str]:
    tools = {"Edit", "Write"}
    if include_apply_patch:
        tools.add("apply_patch")
    if payload.tool_name not in tools:
        return 0, "", ""

    inp = payload.tool_input or {}
    file_path = str(inp.get("file_path") or inp.get("path") or "")
    if not file_path and payload.tool_name != "apply_patch":
        return 0, "", ""

    label = Path(file_path).name if file_path else "patch"
    diff_lines: list[str] = []
    if payload.tool_name == "Edit":
        old = inp.get("old_string", "")
        new = inp.get("new_string", "")
        if old or new:
            diff_lines = diff_edit(old, new, label)
    elif file_path:
        diff_lines = diff_write(file_path, repo=repo)
    elif payload.tool_name == "apply_patch":
        diff_lines = diff_repo(repo, ".")

    if file_path:
        record_edit(state_dir, file_path)
    if not diff_lines:
        return 0, "", ""

    context = hook_context(label, cap(diff_lines, max_diff_lines), message.format(label=label))
    return 0, json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": context,
        }
    }), ""
