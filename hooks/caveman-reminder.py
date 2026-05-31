#!/usr/bin/env python3
"""PostToolUse hook: nudge Claude back to caveman mode if verbose patterns detected.

Exits 2 with a one-line reminder when tool output contains known filler phrases.
install.py wires this into .claude/settings.local.json automatically.
"""
from __future__ import annotations

import json
import re
import os
import sys
from pathlib import Path

def _resolve_repo() -> Path:
    if os.environ.get("LESS_TOKENS_REPO"):
        return Path(os.environ["LESS_TOKENS_REPO"]).resolve()
    curr = Path(__file__).resolve().parent
    for _ in range(4):
        if (curr / "CLAUDE.md").exists() or (curr / ".git").exists():
            return curr
        curr = curr.parent
    return Path(__file__).resolve().parent.parent.parent


REPO = _resolve_repo()

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

    # Support both tool_result and older tool_response keys
    tool_out = payload.get("tool_result") or payload.get("tool_response")
    if not isinstance(tool_out, str):
        return 0

    if _PATTERN.search(tool_out):
        print("Style spec reminder: maintain terse, primitive output. "
              "Avoid filler/conversational phrases.", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
