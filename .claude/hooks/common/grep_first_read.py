"""Shared large-file read gate."""
from __future__ import annotations

import json
import time
from pathlib import Path

try:
    from .payload import HookPayload
    from .search_first import is_indexed, search_was_recent
except ImportError:
    from payload import HookPayload  # type: ignore[no-redef]
    from search_first import is_indexed, search_was_recent  # type: ignore[no-redef]


def _count_lines(p: Path) -> int:
    n = 0
    try:
        with p.open("rb") as f:
            for _ in f:
                n += 1
    except OSError:
        return 0
    return n


def _in_last_search(p: Path, *, ranges_file: Path, window_seconds: int) -> bool:
    try:
        if (time.time() - ranges_file.stat().st_mtime) > window_seconds:
            return False
        data = json.loads(ranges_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    for key in data:
        kp = Path(key)
        if kp == p or str(p).endswith(str(kp)):
            return True
    return False


def _symbol_hint(p: Path) -> str:
    try:
        from symbols import lookup  # type: ignore[import]
        hits = lookup(p.stem)
        if hits:
            return f"  /def {p.stem}  ->  {hits[0]['file']}:{hits[0]['line']}\n"
    except Exception:
        pass
    return ""


def check_grep_first_read(
    payload: HookPayload,
    *,
    repo: Path,
    state_dir: Path,
    config: dict,
) -> tuple[int, str, str]:
    threshold = int(config.get("line_threshold", 150) or 0)
    if not threshold:
        return 0, "", ""
    if payload.tool_name != "Read":
        return 0, "", ""
    inp = payload.tool_input or {}
    if inp.get("offset"):
        return 0, "", ""
    file_path = inp.get("file_path", "")
    if not file_path:
        return 0, "", ""
    p = Path(file_path)
    if not p.exists():
        return 0, "", ""

    window = int(config.get("window_seconds", 300))
    ranges_file = config.get("ranges_file", state_dir / "last-search.json")
    if _in_last_search(p, ranges_file=Path(ranges_file), window_seconds=window):
        return 0, "", ""

    indexed_func = config.get("is_indexed")
    recent_func = config.get("search_was_recent")
    indexed = (
        indexed_func(p)
        if indexed_func
        else is_indexed(
            p,
            repo,
            excluded_prefixes=config.get("excluded_prefixes", ()),
            excluded_names=config.get("excluded_names"),
            indexed_dirs=config.get("dirs", ()),
            root_globs=config.get("root_globs", ("*.md", "*.py", "*.sql")),
        )
    )
    recent = recent_func() if recent_func else search_was_recent(state_dir, window)
    if indexed and not recent:
        return 0, "", ""

    lines = _count_lines(p)
    if lines <= threshold:
        return 0, "", ""

    venv_py = config.get("venv_py", "python3")
    tool_prefix = config.get("tool_prefix", ".claude/tools")
    read_example = config.get(
        "read_example",
        "Read(file_path={file_path!r}, offset=<line>, limit=<n>)",
    )
    hint = _symbol_hint(p)
    msg = (
        f"Grep-first gate: {p.name} is {lines:,} lines (threshold {threshold}).\n"
        f"{hint}"
        f"  {venv_py} {tool_prefix}/symbols.py <name>\n"
        f"  {venv_py} {tool_prefix}/search.py \"<query>\"\n"
        f"Then: {read_example.format(file_path=str(p), start='<line>', limit='<n>')}"
    )
    return 2, "", msg
