#!/usr/bin/env python3
"""PostToolUse hook: truncate oversized Bash, Read, WebFetch, and Glob results."""
from __future__ import annotations

import json
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
    curr = Path.cwd().resolve()
    for _ in range(10):
        if (curr / ".git").exists() or (curr / "CLAUDE.md").exists():
            return curr
        if curr == curr.parent:
            break
        curr = curr.parent
    return Path(__file__).resolve().parent.parent.parent


REPO = _resolve_repo()
sys.path[:0] = [
    str(REPO),
    str(REPO / "agents" / "common" / "hooks"),
    str(REPO / ".claude" / "hooks" / "common"),
    str(REPO / ".claude" / "tools"),
]

try:
    from agents.common.hooks.payload import normalize_claude  # type: ignore[import]
    from agents.common.hooks.truncate_output import check_truncate_output, truncate_bash, truncate_chars, truncate_glob
except Exception:
    from payload import normalize_claude  # type: ignore[no-redef]
    from truncate_output import check_truncate_output, truncate_bash, truncate_chars, truncate_glob  # type: ignore[no-redef]

try:
    from search_config import AGENT_MODEL, MAX_GLOB_RESULTS, MAX_TOOL_OUTPUT_CHARS, TOOL_OUTPUT_HEAD_LINES, TOOL_OUTPUT_TAIL_LINES  # noqa: E402
    from model_profiles import scaled_tool_output_chars  # noqa: E402
    from savings_log import append as _log_savings  # noqa: E402
    from savings_log import resolve_session  # noqa: E402
    MAX_TOOL_OUTPUT_CHARS = scaled_tool_output_chars(MAX_TOOL_OUTPUT_CHARS, AGENT_MODEL)
except Exception:
    MAX_TOOL_OUTPUT_CHARS = 4000
    MAX_GLOB_RESULTS = 100
    TOOL_OUTPUT_HEAD_LINES = 50
    TOOL_OUTPUT_TAIL_LINES = 20

    def _log_savings(_r: dict) -> None:
        pass

    def resolve_session(_raw: dict | None) -> tuple[str, str]:
        return "local-session", "local"


def main() -> int:
    try:
        raw = json.load(sys.stdin)
    except Exception:
        return 0
    payload = normalize_claude(raw)
    code, stdout, stderr = check_truncate_output(
        payload,
        max_chars=MAX_TOOL_OUTPUT_CHARS,
        head_lines=TOOL_OUTPUT_HEAD_LINES,
        tail_lines=TOOL_OUTPUT_TAIL_LINES,
        max_glob_results=MAX_GLOB_RESULTS,
    )
    if code == 2:
        sid, ssrc = resolve_session(raw)
        kept = len(stdout)
        _log_savings({
            "strategy": "truncation",
            "basis": "measured",
            "kept_chars": kept,
            "elided_chars": max(0, len(payload.tool_output) - kept),
            "content_kind": "tool_output",
            "where": payload.tool_name,
            "session_id": sid,
            "session_source": ssrc,
        })
    if stdout:
        print(stdout)
    if stderr:
        print(stderr, file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
