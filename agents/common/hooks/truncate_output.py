"""Shared tool-output truncation logic — agent-neutral."""
from __future__ import annotations

import json

try:
    from .payload import HookPayload
except ImportError:
    from payload import HookPayload  # type: ignore[no-redef]


def truncate_chars(text: str, ceiling: int) -> str:
    if len(text) <= ceiling:
        return text
    head_chars = int(ceiling * 0.6)
    tail_chars = ceiling - head_chars
    omitted = len(text) - head_chars - tail_chars
    return text[:head_chars] + f"\n[... {omitted:,} chars omitted ...]\n" + text[-tail_chars:]


def truncate_bash(text: str, head: int, tail: int, ceiling: int) -> str:
    lines = text.splitlines()
    total = len(lines)
    tail_start = max(head, total - tail)
    kept_head = lines[:head]
    kept_tail = lines[tail_start:]
    omitted_lines = tail_start - head
    if omitted_lines <= 0:
        result = "\n".join(kept_head + kept_tail)
        return truncate_chars(result, ceiling) if len(result) > ceiling else result
    result = (
        "\n".join(kept_head)
        + f"\n[... {omitted_lines:,} lines omitted ...]\n"
        + "\n".join(kept_tail)
    )
    return truncate_chars(result, ceiling) if len(result) > ceiling else result


def truncate_glob(text: str, max_results: int) -> str:
    if max_results <= 0:
        return text
    lines = text.splitlines()
    if len(lines) <= max_results:
        return text
    hidden = len(lines) - max_results
    kept = lines[:max_results]
    kept.append(f"[... {hidden:,} more file(s) — narrow the pattern or use search]")
    return "\n".join(kept)


_TARGETED_TOOLS = {"Bash", "Read", "WebFetch", "Glob", "mcp__filesystem__read_file"}

_SUBAGENT_KEY_MARKERS = (
    "verdict:", "pass:", "fail:", "failed:", "blocker:", "blockers:",
    "recommendation:", "recommend:", "summary:", "confirmed:", "dissent:",
    "extend:", "risk:", "acceptance:", "result:", "outcome:", "status:",
)


def _extract_key_lines(text: str) -> list[str]:
    keep = []
    for line in text.splitlines():
        stripped = line.strip()
        if any(stripped.lower().startswith(marker) for marker in _SUBAGENT_KEY_MARKERS):
            keep.append(stripped)
    return keep


def truncate_subagent(text: str, ceiling: int) -> str:
    """Digest an oversized subagent return: keep pass/fail/blocker-style
    fields verbatim; fall back to head+tail char elision when no such
    fields are present or the digest itself still exceeds the ceiling."""
    if ceiling <= 0 or len(text) <= ceiling:
        return text
    digest = "\n".join(_extract_key_lines(text))
    if digest and len(digest) <= ceiling:
        omitted = len(text) - len(digest)
        return digest + f"\n[... {omitted:,} chars of subagent output omitted; key fields kept ...]"
    return truncate_chars(text, ceiling)


def check_truncate_subagent(payload: HookPayload, *, max_chars: int) -> tuple[int, str, str]:
    """Return (exit_code, stdout, stderr) for a PostToolUse:Task hook."""
    if payload.tool_name != "Task":
        return 0, "", ""

    text = payload.tool_output
    if not isinstance(text, str):
        text = json.dumps(text)

    if max_chars == 0 or len(text) <= max_chars:
        return 0, "", ""

    truncated = truncate_subagent(text, max_chars)
    omitted = len(text) - len(truncated)
    if omitted > 0:
        return 2, truncated, f"[subagent-cap — {omitted:,} chars omitted ({len(text):,} total)]"
    return 0, "", ""


def check_truncate_output(
    payload: HookPayload,
    *,
    max_chars: int,
    head_lines: int,
    tail_lines: int,
    max_glob_results: int,
) -> tuple[int, str, str]:
    """Return (exit_code, stdout, stderr)."""
    tool = payload.tool_name
    if tool not in _TARGETED_TOOLS:
        return 0, "", ""

    text = payload.tool_output
    if not isinstance(text, str):
        text = json.dumps(text)

    if tool == "Glob":
        truncated = truncate_glob(text, max_glob_results)
        if truncated != text:
            omitted = len(text) - len(truncated)
            return 2, truncated, f"[glob-cap — {omitted:,} chars omitted]"
        return 0, "", ""

    if max_chars == 0 or len(text) <= max_chars:
        return 0, "", ""

    if tool == "Bash":
        truncated = truncate_bash(text, head_lines, tail_lines, max_chars)
    else:
        truncated = truncate_chars(text, max_chars)

    omitted = len(text) - len(truncated)
    if omitted > 0:
        return 2, truncated, f"[truncated — {omitted:,} chars omitted ({len(text):,} total)]"
    return 0, "", ""
