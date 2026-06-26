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


def _display_path(path: Path, repo: Path) -> str:
    try:
        if path.is_absolute():
            return path.resolve().relative_to(repo.resolve()).as_posix()
    except Exception:
        pass
    return path.as_posix()


def _diff_touched_files(repo: Path, touched_files: tuple[Path, ...]) -> list[str]:
    diff_lines: list[str] = []
    for path in touched_files:
        pathspec = _display_path(path, repo)
        diff_lines.extend(diff_repo(repo, pathspec))
    return diff_lines


def _diff_file_from_line(line: str) -> str | None:
    if line.startswith("diff --git "):
        parts = line.strip().split()
        if len(parts) >= 4:
            return parts[3].removeprefix("b/")
    if line.startswith("+++ b/"):
        return line.strip()[6:]
    return None


def compact_hunk_summary(diff_lines: list[str], touched_files: tuple[Path, ...], repo: Path) -> str:
    """Summarize touched files and hunk sizes before any full apply_patch diff."""
    touched = [_display_path(path, repo) for path in touched_files]
    stats: dict[str, dict[str, int]] = {}
    current = touched[0] if len(touched) == 1 else ""
    for line in diff_lines:
        file_from_line = _diff_file_from_line(line)
        if file_from_line:
            current = file_from_line
            stats.setdefault(current, {"hunks": 0, "added": 0, "removed": 0})
            continue
        if not current:
            continue
        stats.setdefault(current, {"hunks": 0, "added": 0, "removed": 0})
        if line.startswith("@@"):
            stats[current]["hunks"] += 1
        elif line.startswith("+") and not line.startswith("+++"):
            stats[current]["added"] += 1
        elif line.startswith("-") and not line.startswith("---"):
            stats[current]["removed"] += 1

    lines = ["apply_patch touched files:"]
    if touched:
        lines.extend(f"- {path}" for path in touched)
    else:
        lines.append("- unknown; parsed paths unavailable")
    if stats:
        lines.extend(["", "compact hunk summary:"])
        for path in sorted(stats):
            s = stats[path]
            lines.append(f"- {path}: {s['hunks']} hunk(s), +{s['added']} -{s['removed']}")
    return "\n".join(lines) + "\n"


def apply_patch_diff_text(
    payload: HookPayload,
    *,
    repo: Path,
    max_chars: int,
) -> str:
    diff_lines = _diff_touched_files(repo, payload.touched_files) if payload.touched_files else diff_repo(repo, ".")
    summary = compact_hunk_summary(diff_lines, payload.touched_files, repo)
    full = "".join(diff_lines)
    if not full:
        return summary
    if max_chars <= 0 or len(full) <= max_chars:
        return summary + "\nfull diff:\n" + full
    return (
        summary
        + "\nfull diff omitted: "
        + f"{len(full)} chars exceeds Codex apply_patch cap {max_chars}. "
        + "Use targeted git diff for a touched file if needed.\n"
    )


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
        data[file_path] = time.time()
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
    apply_patch_max_chars: int = 0,
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
    diff_text = ""
    if payload.tool_name == "Edit":
        old = inp.get("old_string", "")
        new = inp.get("new_string", "")
        if old or new:
            diff_lines = diff_edit(old, new, label)
    elif file_path:
        diff_lines = diff_write(file_path, repo=repo)
    elif payload.tool_name == "apply_patch":
        diff_text = apply_patch_diff_text(payload, repo=repo, max_chars=apply_patch_max_chars)

    if file_path:
        record_edit(state_dir, file_path)
    elif payload.tool_name == "apply_patch":
        for path in payload.touched_files:
            record_edit(state_dir, str(path if path.is_absolute() else repo / path))
    if not diff_lines and not diff_text:
        return 0, "", ""

    context = hook_context(label, diff_text or cap(diff_lines, max_diff_lines), message.format(label=label))
    return 0, json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": context,
        }
    }), ""
