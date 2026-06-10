"""Shared compact-trigger logic — agent-neutral."""
from __future__ import annotations

import os
from pathlib import Path

from .payload import HookPayload


def check_compact_trigger(
    payload: HookPayload,
    *,
    state_dir: Path,
    max_session_chars: int,
    message: str,
) -> tuple[int, str, str]:
    """Return (exit_code, stdout, stderr)."""
    if max_session_chars == 0:
        return 0, "", ""

    transcript_path = payload.transcript_path
    if not transcript_path:
        return 0, "", ""

    try:
        size = os.path.getsize(transcript_path)
    except OSError:
        return 0, "", ""

    if size <= max_session_chars:
        return 0, "", ""

    state_file = state_dir / "compact-trigger-last"
    try:
        last = int(state_file.read_text().strip())
    except Exception:
        last = 0

    hysteresis = max_session_chars // 4
    if last and size < last + hysteresis:
        return 0, "", ""

    try:
        state_dir.mkdir(parents=True, exist_ok=True)
        state_file.write_text(str(size))
    except Exception:
        pass

    return 2, "", message.format(size=size, threshold=max_session_chars)
