#!/usr/bin/env python3
"""Stop hook: enforce caveman (terse) output on Claude's actual response.

The previous version was a PostToolUse hook that scanned *tool output* for
filler — but filler lives in Claude's prose, not in tool results, so it almost
never fired. This reads the last assistant turn from `transcript_path` and
checks the text Claude actually wrote: filler phrases + a prose word ceiling
(code fences exempt). Exits 2 with a terse nudge so Claude revises.

A `stop_hook_active` guard prevents an infinite stop loop. Disable via
CAVEMAN_ENFORCE in search_config.py.
install.py wires this as a Stop hook under --caveman.
"""
from __future__ import annotations

import json
import os
import re
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
    curr = Path.cwd().resolve()
    for _ in range(10):
        if (curr / ".git").exists() or (curr / "CLAUDE.md").exists():
            return curr
        if curr == curr.parent:
            break
        curr = curr.parent
    return Path(__file__).resolve().parent.parent.parent


REPO = _resolve_repo()
sys.path.insert(0, str(REPO / ".claude" / "tools"))

try:
    from search_config import CAVEMAN_ENFORCE, MAX_RESPONSE_WORDS
except Exception:
    CAVEMAN_ENFORCE = True
    MAX_RESPONSE_WORDS = 600

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

_FENCE = re.compile(r"```.*?```", re.DOTALL)
_INLINE = re.compile(r"`[^`]*`")


def last_assistant_text(transcript_path: str) -> str:
    """Concatenated text of the last assistant turn in a JSONL transcript."""
    try:
        lines = Path(transcript_path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except Exception:
            continue
        if ev.get("type") != "assistant":
            continue
        msg = ev.get("message", ev)
        content = msg.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = [b.get("text", "") for b in content
                     if isinstance(b, dict) and b.get("type") == "text"]
            return "\n".join(p for p in parts if p)
        return ""
    return ""


def analyze(text: str) -> list[str]:
    """Return a list of caveman violations in the assistant prose (empty = clean)."""
    if not text:
        return []
    prose = _INLINE.sub(" ", _FENCE.sub(" ", text))
    problems = []
    fillers = sorted({m.group(0).lower() for m in _PATTERN.finditer(prose)})
    if fillers:
        problems.append("filler: " + ", ".join(fillers))
    if MAX_RESPONSE_WORDS:
        words = len(re.findall(r"\b\w+\b", prose))
        if words > MAX_RESPONSE_WORDS:
            problems.append(f"{words} prose words > {MAX_RESPONSE_WORDS} budget")
    return problems


def main() -> int:
    if not CAVEMAN_ENFORCE:
        return 0
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if payload.get("stop_hook_active"):
        return 0  # already re-prompted once — don't loop
    text = last_assistant_text(payload.get("transcript_path", ""))
    problems = analyze(text)
    if problems:
        print("Caveman mode: revise last response — " + "; ".join(problems)
              + ". Cut filler and padding; short sentences; stop when done.",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
