"""Shared auto-slice logic for reads after search results."""
from __future__ import annotations

import json
import time
from pathlib import Path

try:
    from .payload import HookPayload
except ImportError:
    from payload import HookPayload  # type: ignore[no-redef]


def ranges_for(file_path: str, *, ranges_file: Path, window_seconds: int) -> list[list[int]]:
    """Matched line ranges for file_path from a recent search."""
    try:
        if (time.time() - ranges_file.stat().st_mtime) > window_seconds:
            return []
        data = json.loads(ranges_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    p = Path(file_path)
    for key, spans in data.items():
        kp = Path(key)
        if kp == p or str(p).endswith(str(kp)):
            return spans or []
    return []


def check_auto_slice(
    payload: HookPayload,
    *,
    state_dir: Path,
    window_seconds: int,
    read_example: str,
) -> tuple[int, str, str]:
    """Return (exit_code, stdout, stderr)."""
    if payload.tool_name != "Read":
        return 0, "", ""
    inp = payload.tool_input or {}
    if inp.get("offset"):
        return 0, "", ""
    fp = inp.get("file_path", "")
    if not fp:
        return 0, "", ""
    spans = ranges_for(fp, ranges_file=state_dir / "last-search.json", window_seconds=window_seconds)
    if not spans:
        return 0, "", ""

    start, end = spans[0]
    limit = max(1, end - start + 1)
    extra = f" (plus {len(spans) - 1} more matched range(s) in this file)" if len(spans) > 1 else ""
    msg = (
        f"Auto-slice: your last search matched {Path(fp).name} at lines "
        f"{start}-{end}{extra}. Read only that slice:\n"
        f"  {read_example.format(file_path=fp, start=start, limit=limit)}\n"
        "To read the whole file anyway, pass an explicit offset."
    )
    return 2, "", msg
