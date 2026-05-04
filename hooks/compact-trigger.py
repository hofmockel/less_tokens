#!/usr/bin/env python3
"""PostToolUse hook: nudge Claude to /compact when the session transcript grows large.

Claude Code writes a per-session JSONL transcript and passes its path to hooks
as `transcript_path`. When that file exceeds MAX_SESSION_CHARS, this hook exits
2 with a one-line reminder so Claude runs /compact before the next tool call.

Hysteresis: writes the size at fire time to .claude/state/compact-trigger-last
and only re-fires after the transcript grows by another MAX_SESSION_CHARS // 4.
This prevents the reminder firing on every subsequent tool call once tripped.

Wire in .claude/settings.local.json:

    {
      "hooks": {
        "PostToolUse": [
          {"matcher": ".*",
           "hooks": [{"type": "command",
                      "command": "<VENV_PY> .claude/hooks/compact-trigger.py"}]}
        ]
      }
    }

Tune in tools/search_config.py: MAX_SESSION_CHARS = 500_000  # ~125k tokens
Set MAX_SESSION_CHARS = 0 to disable without unwiring the hook.
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
except Exception:
    MAX_SESSION_CHARS = 500_000

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
    print(f"Session transcript is now {size:,} chars (threshold {MAX_SESSION_CHARS:,}). "
          f"Run /compact before the next tool call to reclaim context budget.",
          file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
