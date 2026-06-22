"""Shared search-first gate logic — agent-neutral."""
from __future__ import annotations

import fnmatch
import re
import time
from pathlib import Path

try:
    from .payload import HookPayload
except ImportError:
    from payload import HookPayload  # type: ignore[no-redef]


def is_indexed(
    path: Path,
    repo: Path,
    *,
    excluded_prefixes: tuple[str, ...] = (),
    excluded_names: set[str] | None = None,
    indexed_dirs: tuple[str, ...] = (),
    root_globs: tuple[str, ...] = ("*.md", "*.py", "*.sql"),
) -> bool:
    try:
        rel = path.resolve().relative_to(repo).as_posix()
    except ValueError:
        return False

    if excluded_names is None:
        excluded_names = set()

    parts = set(Path(rel).parts)
    if parts & excluded_names:
        return False
    if any(rel.startswith(p) for p in excluded_prefixes):
        return False

    if "/" not in rel:
        return any(fnmatch.fnmatch(rel, g) for g in root_globs)
    if any(rel.startswith(d) for d in indexed_dirs):
        return rel.endswith((".py", ".sql"))
    return False


def search_was_recent(state_dir: Path, window_seconds: int) -> bool:
    state_file = state_dir / "last-search"
    try:
        mtime = state_file.stat().st_mtime
    except OSError:
        return False
    return (time.time() - mtime) < window_seconds


def _symbol_exists(name: str, repo: Path) -> bool:
    try:
        import sys
        sys.path.insert(0, str(repo / ".less_tokens" / "tools"))
        sys.path.insert(0, str(repo / ".claude" / "tools"))
        from symbols import has_symbol  # type: ignore[import]
        return has_symbol(name)
    except Exception:
        return False


def check_search_first(
    payload: HookPayload,
    *,
    repo: Path,
    state_dir: Path,
    config: dict,
) -> tuple[int, str, str]:
    """Return (exit_code, stdout, stderr)."""
    tool = payload.tool_name
    tool_prefix = config.get("tool_prefix", ".claude/tools")

    if tool == "Grep":
        pat = (payload.tool_input or {}).get("pattern", "")
        name = pat.strip()
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) and _symbol_exists(name, repo):
            venv_py = config.get("venv_py", "python3")
            ctx = (
                f"`{name}` is a defined symbol. For its definition, "
                f"`/def {name}` ({venv_py} {tool_prefix}/symbols.py {name}) returns the exact "
                f"file:line + a Read(offset,limit) — cheaper than grepping. "
                f"Grep is fine if you want usages."
            )
            import json
            return 0, json.dumps({"hookSpecificOutput": {
                "hookEventName": "PreToolUse", "additionalContext": ctx}}), ""
        return 0, "", ""

    if tool != "Read":
        return 0, "", ""

    file_path = (payload.tool_input or {}).get("file_path", "")
    if not file_path:
        return 0, "", ""

    p = Path(file_path)
    if not is_indexed(
        p, repo,
        excluded_prefixes=config.get("excluded_prefixes", ()),
        excluded_names=config.get("excluded_names"),
        indexed_dirs=config.get("dirs", ()),
        root_globs=config.get("root_globs", ("*.md", "*.py", "*.sql")),
    ):
        return 0, "", ""

    if search_was_recent(state_dir, config.get("window_seconds", 300)):
        return 0, "", ""

    venv_py = config.get("venv_py", "python3")
    try:
        rel = p.resolve().relative_to(repo).as_posix()
    except ValueError:
        rel = str(file_path)

    msg = (
        f"Search-first rule: {rel} is indexed.\n"
        f"Run vector search before Read:\n"
        f"  {venv_py} {tool_prefix}/search.py \"<your query>\"\n"
        f"After a search, Reads on indexed files are allowed for "
        f"{config.get('window_seconds', 300)}s."
    )
    return 2, "", msg
