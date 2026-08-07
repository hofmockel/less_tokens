"""Shared concise-response analysis for Claude and Codex."""

from __future__ import annotations

import json
import re
from pathlib import Path

VERBOSE_PATTERNS = [
    r"\bI apologize\b",
    r"\bI'm sorry\b",
    r"\bCertainly[,!.]?",
    r"\bAbsolutely[,!.]?",
    r"\bI'd be happy to\b",
    r"\bI'd be glad to\b",
    r"\bGreat question\b",
    r"\bOf course[,!.]?",
    r"\bI understand that\b",
    r"\bThank you for\b",
    r"\bI hope this helps\b",
    r"\bPlease let me know if\b",
    r"\bFeel free to\b",
    r"\bAs an AI\b",
    r"\bAs a language model\b",
    r"\bPlease note that\b",
    r"\bIt's worth noting\b",
    r"\bIn conclusion\b",
    r"\bTo summarize\b",
]

_PATTERN = re.compile("|".join(VERBOSE_PATTERNS), re.IGNORECASE)
_FENCE = re.compile(r"```.*?(?:```|\Z)", re.DOTALL)
_INLINE = re.compile(r"`[^`]*`")
_QUOTED = re.compile(r'"[^"]*"|\'[^\']*\'')

# Explicit, user-requested exemption for a document/report/proposal draft pasted directly in
# the reply (not fenced, not written via Write/Edit). Set only when the user's own message
# asked for one — never on the assistant's own judgment of its output's length or importance.
DOCUMENT_DRAFT_SENTINEL = "<!-- less-tokens: document-draft -->"


def last_assistant_text(transcript_path: str) -> str:
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
            parts = [
                b.get("text", "")
                for b in content
                if isinstance(b, dict) and b.get("type") == "text"
            ]
            return "\n".join(p for p in parts if p)
        return ""
    return ""


def analyze(
    text: str, *, max_response_words: int, min_filler_hits: int = 1
) -> list[str]:
    if not text:
        return []
    if DOCUMENT_DRAFT_SENTINEL in text:
        return []
    prose = _QUOTED.sub(" ", _INLINE.sub(" ", _FENCE.sub(" ", text)))
    problems = []
    fillers = sorted({m.group(0).lower() for m in _PATTERN.finditer(prose)})
    if len(fillers) >= min_filler_hits:
        problems.append("filler: " + ", ".join(fillers))
    if max_response_words:
        words = len(re.findall(r"\b\w+\b", prose))
        if words > max_response_words:
            problems.append(f"{words} prose words > {max_response_words} budget")
    return problems
