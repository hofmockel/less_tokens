#!/usr/bin/env python3
"""PostToolUse hook: nudge Claude back to caveman mode if verbose patterns detected.

Receives the tool result JSON on stdin. If the assistant response contains
typical verbosity markers, exits 2 with a one-line reminder so the model
corrects its next output.

Wire in .claude/settings.local.json:

    {
      "hooks": {
        "PostToolUse": [
          {"matcher": ".*",
           "hooks": [{"type": "command",
                      "command": "<VENV_PY> .claude/hooks/caveman-reminder.py"}]}
        ]
      }
    }
"""
from __future__ import annotations

import json
import re
import sys

VERBOSE_PATTERNS = [
    r"\bI apologize\b",
    r"\bI'm sorry\b",
    r"\bCertainly[,!]",
    r"\bAbsolutely[,!]",
    r"\bI'd be happy to\b",
    r"\bI'd be glad to\b",
    r"\bGreat question\b",
    r"\bOf course[,!]",
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

    response = payload.get("tool_response", "") or ""
    if isinstance(response, dict):
        response = json.dumps(response)

    if _PATTERN.search(response):
        print("Caveman mode on. Short sentence. No filler.", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
