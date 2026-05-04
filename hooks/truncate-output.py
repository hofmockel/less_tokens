#!/usr/bin/env python3
"""PostToolUse hook: truncate oversized tool results to stay within token budget.

Fires on Bash, Read, and WebFetch results. If the result exceeds
MAX_TOOL_OUTPUT_CHARS, emits a truncated version and exits 2 so Claude sees
the shorter output instead of the full one.

- Bash: head+tail (lines-based) — preserves start and bottom errors
- Read / WebFetch: 60/40 character split — preserves file header and tail

Wire in .claude/settings.local.json — place before caveman-reminder entry:

    {
      "hooks": {
        "PostToolUse": [
          {"matcher": "Bash|Read|WebFetch",
           "hooks": [{"type": "command",
                      "command": "<VENV_PY> .claude/hooks/truncate-output.py"}]}
        ]
      }
    }

Tune ceiling in tools/search_config.py: MAX_TOOL_OUTPUT_CHARS = 4000
Set to 0 to disable without removing the hook.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "tools"))

try:
    from search_config import (
        MAX_TOOL_OUTPUT_CHARS,
        TOOL_OUTPUT_HEAD_LINES,
        TOOL_OUTPUT_TAIL_LINES,
    )
except Exception:
    MAX_TOOL_OUTPUT_CHARS = 4000
    TOOL_OUTPUT_HEAD_LINES = 50
    TOOL_OUTPUT_TAIL_LINES = 20

_TARGETED_TOOLS = {"Bash", "Read", "WebFetch"}


def truncate_chars(text: str, ceiling: int) -> str:
    """Keep first 60% and last 40% of ceiling chars with an omission marker."""
    if len(text) <= ceiling:
        return text
    head_chars = int(ceiling * 0.6)
    tail_chars = ceiling - head_chars
    omitted = len(text) - head_chars - tail_chars
    return text[:head_chars] + f"\n[... {omitted:,} chars omitted ...]\n" + text[-tail_chars:]


def truncate_bash(text: str, head: int, tail: int, ceiling: int) -> str:
    """Keep first HEAD and last TAIL lines; fall back to char split if still over ceiling."""
    lines = text.splitlines()
    total = len(lines)
    tail_start = max(head, total - tail)
    kept_head = lines[:head]
    kept_tail = lines[tail_start:]
    omitted_lines = tail_start - head
    if omitted_lines <= 0:
        return truncate_chars(text, ceiling)
    result = "\n".join(kept_head) + f"\n[... {omitted_lines:,} lines omitted ...]\n" + "\n".join(kept_tail)
    if len(result) > ceiling:
        return truncate_chars(result, ceiling)
    return result


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    tool_name = payload.get("tool_name", "")
    if tool_name not in _TARGETED_TOOLS:
        return 0

    tool_result = payload.get("tool_result", "")
    if isinstance(tool_result, dict):
        tool_result = json.dumps(tool_result)
    elif not isinstance(tool_result, str):
        tool_result = str(tool_result)

    if MAX_TOOL_OUTPUT_CHARS == 0 or len(tool_result) <= MAX_TOOL_OUTPUT_CHARS:
        return 0

    if tool_name == "Bash":
        truncated = truncate_bash(tool_result, TOOL_OUTPUT_HEAD_LINES, TOOL_OUTPUT_TAIL_LINES, MAX_TOOL_OUTPUT_CHARS)
    else:
        truncated = truncate_chars(tool_result, MAX_TOOL_OUTPUT_CHARS)

    omitted_chars = len(tool_result) - len(truncated)
    print(truncated)
    print(f"[truncated — {omitted_chars:,} chars omitted ({len(tool_result):,} total)]",
          file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
