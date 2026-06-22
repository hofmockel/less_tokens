"""Deterministic summaries for oversized context."""
from __future__ import annotations

import re

SIGNAL_RE = re.compile(
    r"(Traceback|File \".+\", line \d+|FAILED\s+\S+|ERROR\s+\S+|AssertionError|"
    r"\bassert\b|^\s*E\s+|error:|warning:|Exception|\.py:\d+|\.ts:\d+|\.js:\d+)",
    re.IGNORECASE,
)


def summarize_lines(text: str, *, max_lines: int = 40) -> str:
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    head = lines[: max_lines // 2]
    tail = lines[-(max_lines - len(head)) :]
    omitted = len(lines) - len(head) - len(tail)
    return "\n".join([*head, f"... {omitted} line(s) omitted ...", *tail])


def summarize_tool_output(
    text: str,
    *,
    command: str = "",
    max_lines: int = 80,
    max_chars: int = 4000,
) -> str:
    """Summarize tool output while preserving actionable failure signal."""
    lines = text.splitlines()
    if len(text) <= max_chars and len(lines) <= max_lines:
        return text

    kept: list[str] = []
    if command:
        kept.append(f"$ {command}")

    signal_lines = [line for line in lines if SIGNAL_RE.search(line)]
    for line in signal_lines:
        if line not in kept:
            kept.append(line)

    kept.extend(line for line in lines[: min(12, len(lines))] if line not in kept)

    tail = lines[-min(20, len(lines)) :]
    for line in tail:
        if line not in kept:
            kept.append(line)

    summary = _cap_lines(kept, max_lines)
    omitted_lines = max(0, len(lines) - len(summary.splitlines()))
    prefix = f"[less_tokens summary: {omitted_lines:,} line(s) omitted]"
    summary = prefix + "\n" + summary
    if len(summary) <= max_chars:
        return summary
    return summary[: max(0, max_chars - 1)].rstrip() + "…"


def _cap_lines(lines: list[str], max_lines: int) -> str:
    if len(lines) <= max_lines:
        return "\n".join(lines)
    head_count = max_lines // 2
    tail_count = max_lines - head_count
    omitted = len(lines) - head_count - tail_count
    return "\n".join([
        *lines[:head_count],
        f"... {omitted} selected line(s) omitted ...",
        *lines[-tail_count:],
    ])
