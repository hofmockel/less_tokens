#!/usr/bin/env python3
"""PostToolUse hook: nudge Claude to /compact when session transcript grows large.

Exits 2 with a reminder when transcript_path exceeds MAX_SESSION_CHARS.
Hysteresis: only re-fires after another MAX_SESSION_CHARS // 4 of growth.
Tune threshold in search_config.py. Set to 0 to disable.
install.py wires this into .claude/settings.local.json automatically.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "tools"))

try:
    from search_config import MAX_SESSION_CHARS
    from savings_log import append as _log_savings
except Exception:
    MAX_SESSION_CHARS = 500_000
    def _log_savings(_r: dict) -> None: pass  # noqa: E301

STATE_FILE = REPO / ".claude" / "state" / "compact-trigger-last"


def read_last_size() -> int:
    try:
        return int(STATE_FILE.read_text().strip())
    except Exception:
        return 0


def write_last_size(size: int) -> None:
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(str(size))
    except Exception:
        pass


def main() -> int:
    if MAX_SESSION_CHARS == 0:
        return 0

    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    transcript_path = payload.get("transcript_path")
    if not transcript_path:
        return 0

    try:
        size = os.path.getsize(transcript_path)
    except OSError:
        return 0

    if size <= MAX_SESSION_CHARS:
        return 0

    last = read_last_size()
    hysteresis = MAX_SESSION_CHARS // 4
    if last and size < last + hysteresis:
        return 0

    write_last_size(size)
    _log_savings({"strategy": "compaction", "transcript_chars": size, "saved_chars": 0})
    print(f"Session transcript is now {size:,} chars (threshold {MAX_SESSION_CHARS:,}). "
          f"Run /compact before the next tool call to reclaim context budget.",
          file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
