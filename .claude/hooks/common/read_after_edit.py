"""Shared read-after-edit guard."""
from __future__ import annotations

import json
import time
from pathlib import Path

try:
    from .payload import HookPayload
except ImportError:
    from payload import HookPayload  # type: ignore[no-redef]


def _load_edits(state_dir: Path) -> dict[str, float]:
    try:
        return json.loads((state_dir / "last-edit.json").read_text())
    except Exception:
        return {}


def check_read_after_edit(
    payload: HookPayload,
    *,
    state_dir: Path,
    window_seconds: int,
) -> tuple[int, str, str]:
    if not window_seconds:
        return 0, "", ""
    if payload.tool_name != "Read":
        return 0, "", ""
    inp = payload.tool_input or {}
    if inp.get("offset") is not None:
        return 0, "", ""
    file_path = inp.get("file_path", "")
    if not file_path:
        return 0, "", ""
    edit_ts = _load_edits(state_dir).get(str(Path(file_path).resolve()))
    if edit_ts is None:
        return 0, "", ""
    age = time.time() - edit_ts
    if age > window_seconds:
        return 0, "", ""
    label = Path(file_path).name
    msg = (
        f"read-after-edit: {label} was edited {age:.0f}s ago — diff already in context. "
        "Skip the whole-file reread; use the diff or read a targeted slice."
    )
    return 2, "", msg
