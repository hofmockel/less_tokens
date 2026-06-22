"""Deterministic summaries for oversized context."""
from __future__ import annotations


def summarize_lines(text: str, *, max_lines: int = 40) -> str:
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    head = lines[: max_lines // 2]
    tail = lines[-(max_lines - len(head)) :]
    omitted = len(lines) - len(head) - len(tail)
    return "\n".join([*head, f"... {omitted} line(s) omitted ...", *tail])
