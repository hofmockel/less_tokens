#!/usr/bin/env python3
"""PostToolUse:Task hook: cap an oversized subagent return before it lands
in the parent's transcript (SA1)."""

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
    from agents.common.hooks.truncate_output import check_truncate_subagent
except Exception:
    from payload import normalize_claude  # type: ignore[no-redef]
    from truncate_output import check_truncate_subagent  # type: ignore[no-redef]

try:
    from search_config import MAX_SUBAGENT_OUTPUT_CHARS  # noqa: E402
    from savings_log import append as _log_savings  # noqa: E402
    from savings_log import resolve_session  # noqa: E402
    from savings_log import STRATEGY_SUBAGENT_CAP  # noqa: E402
except Exception:
    MAX_SUBAGENT_OUTPUT_CHARS = 6000
    STRATEGY_SUBAGENT_CAP = "subagent-cap"

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
    code, stdout, stderr = check_truncate_subagent(
        payload, max_chars=MAX_SUBAGENT_OUTPUT_CHARS
    )
    if code == 2:
        sid, ssrc = resolve_session(raw)
        kept = len(stdout)
        _log_savings(
            {
                "strategy": STRATEGY_SUBAGENT_CAP,
                "basis": "measured",
                "kept_chars": kept,
                "elided_chars": max(0, len(payload.tool_output) - kept),
                "content_kind": "subagent_output",
                "where": payload.tool_name,
                "session_id": sid,
                "session_source": ssrc,
            }
        )
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PostToolUse",
                        "updatedToolOutput": stdout,
                        "additionalContext": stderr,
                    }
                }
            )
        )
        return 0
    return code


if __name__ == "__main__":
    sys.exit(main())
