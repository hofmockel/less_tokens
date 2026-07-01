#!/usr/bin/env python3
"""Codex PostToolUse hook: truncate oversized Bash and filesystem tool results."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _resolve_repo() -> Path:
    if os.environ.get("LESS_TOKENS_REPO"):
        return Path(os.environ["LESS_TOKENS_REPO"]).resolve()
    curr = Path(__file__).resolve().parent
    for _ in range(6):
        if (curr / ".git").exists() or (curr / "AGENTS.md").exists():
            return curr
        curr = curr.parent
    return Path(__file__).resolve().parent.parent.parent.parent


REPO = _resolve_repo()
sys.path.insert(0, str(REPO / ".less_tokens" / "hooks"))
sys.path.insert(0, str(REPO / "agents" / "common" / "hooks"))
sys.path.insert(0, str(REPO / ".less_tokens" / "tools"))
sys.path.insert(0, str(REPO / ".claude" / "tools"))

from payload import normalize_codex  # noqa: E402
from truncate_output import check_truncate_output  # noqa: E402

try:
    from savings_log import append as _log_savings  # noqa: E402
    from savings_log import resolve_session  # noqa: E402
    from savings_log import STRATEGY_TRUNCATION  # noqa: E402
except Exception:
    STRATEGY_TRUNCATION = "truncation"

    def _log_savings(_r: dict) -> None:
        pass

    def resolve_session(_raw: dict | None) -> tuple[str, str]:
        return "local-session", "local"

try:
    from search_config import (  # noqa: E402
        MAX_GLOB_RESULTS,
    )
except Exception:
    MAX_GLOB_RESULTS = 100

try:
    from search_config import (  # noqa: E402
        CODEX_MAX_TOOL_OUTPUT_CHARS,
        CODEX_MAX_FILESYSTEM_READ_CHARS,
        CODEX_TOOL_OUTPUT_HEAD_LINES,
        CODEX_TOOL_OUTPUT_TAIL_LINES,
    )
except Exception:
    CODEX_MAX_TOOL_OUTPUT_CHARS = 1500
    CODEX_MAX_FILESYSTEM_READ_CHARS = 1200
    CODEX_TOOL_OUTPUT_HEAD_LINES = 30
    CODEX_TOOL_OUTPUT_TAIL_LINES = 20


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _cap_for_tool(tool_name: str) -> int:
    if tool_name == "mcp__filesystem__read_file":
        return _env_int("LESS_TOKENS_CODEX_MAX_FILESYSTEM_READ_CHARS", CODEX_MAX_FILESYSTEM_READ_CHARS)
    return _env_int("LESS_TOKENS_CODEX_MAX_TOOL_OUTPUT_CHARS", CODEX_MAX_TOOL_OUTPUT_CHARS)


def _line_cap(name: str, default: int) -> int:
    return _env_int(name, default)

raw = json.loads(sys.stdin.read())
payload = normalize_codex(raw)
code, stdout, stderr = check_truncate_output(
    payload,
    max_chars=_cap_for_tool(payload.tool_name),
    head_lines=_line_cap("LESS_TOKENS_CODEX_TOOL_OUTPUT_HEAD_LINES", CODEX_TOOL_OUTPUT_HEAD_LINES),
    tail_lines=_line_cap("LESS_TOKENS_CODEX_TOOL_OUTPUT_TAIL_LINES", CODEX_TOOL_OUTPUT_TAIL_LINES),
    max_glob_results=MAX_GLOB_RESULTS,
)
if stdout:
    sid, ssrc = resolve_session(raw)
    _log_savings({
        "strategy": STRATEGY_TRUNCATION,
        "basis": "measured",
        "kept_chars": len(stdout),
        "elided_chars": max(0, len(payload.tool_output) - len(stdout)),
        "content_kind": "tool_output",
        "where": payload.tool_name,
        "session_id": sid,
        "session_source": ssrc,
    })
    print(stdout)
if stderr:
    print(stderr, file=sys.stderr)
sys.exit(code)
