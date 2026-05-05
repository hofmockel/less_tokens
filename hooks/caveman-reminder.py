#!/usr/bin/env python3
"""PostToolUse hook: nudge Claude back to caveman mode if verbose patterns detected.

Exits 2 with a one-line reminder when tool output contains known filler phrases.
install.py wires this into .claude/settings.local.json automatically.
"""
from __future__ import annotations

import json
import re
import sys

VERBOSE_PATTERNS = [
    r"\bI apologize\b",
    r"\bI'm sorry\b",
    r"\bCertainly[,!.]",
    r"\bAbsolutely[,!.]",
    r"\bI'd be happy to\b",
    r"\bI'd be glad to\b",
    r"\bGreat question\b",
    r"\bOf course[,!.]",
    r"\bI understand that\b",
    r"\bThank you for\b",
    r"\bI hope this helps\b",
    r"\bPlease let me know if\b",
    r"\bFeel free to\b",
]

_PATTERN = re.compile("|".join(VERBOSE_PATTERNS), re.IGNORECASE)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    # Hooks receive tool output, not assistant prose — this fires on tool results
    # containing filler patterns (rare) and serves as a periodic in-context nudge.
    tool_output = payload.get("tool_response") or payload.get("tool_result") or ""
    if isinstance(tool_output, dict):
        tool_output = json.dumps(tool_output)
    elif not isinstance(tool_output, str):
        tool_output = str(tool_output)

    if _PATTERN.search(tool_output):
        print("Caveman mode on. Short sentence. No filler.", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
