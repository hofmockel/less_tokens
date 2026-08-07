#!/usr/bin/env python3
"""PreToolUse+PostToolUse:Task hook (SA2): log subagent fan-out telemetry —
prompt size at spawn, return size at completion, paired into one event."""

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
    from agents.common.hooks.payload import normalize_claude
    from agents.common.hooks.subagent_fanout import (  # noqa: F401
        handle_post_return,
        handle_pre_spawn,
        pop_spawn,
        record_spawn,
        spawn_key,
        subagent_type_of,
    )
except Exception:
    from payload import normalize_claude  # type: ignore[no-redef]
    from subagent_fanout import (  # type: ignore[no-redef]  # noqa: F401
        handle_post_return,
        handle_pre_spawn,
        pop_spawn,
        record_spawn,
        spawn_key,
        subagent_type_of,
    )

try:
    from search_config import active_state_dir as _active_state_dir  # noqa: E402
except Exception:

    def _active_state_dir() -> Path:  # type: ignore[misc]
        return REPO / ".claude" / "state"


try:
    from savings_log import append as _log_savings  # noqa: E402
    from savings_log import resolve_session  # noqa: E402
except Exception:

    def _log_savings(_r: dict) -> None:
        pass

    def resolve_session(_raw: dict | None) -> tuple[str, str]:
        return "local-session", "local"


def main() -> int:
    try:
        raw = json.load(sys.stdin)
    except Exception:
        return 0
    if raw.get("tool_name") != "Task":
        return 0

    tool_input = raw.get("tool_input") or {}
    event = str(raw.get("hook_event_name") or raw.get("hookEventName") or "")

    if event == "PreToolUse":
        handle_pre_spawn(_active_state_dir(), tool_input)
        return 0

    if event == "PostToolUse":
        payload = normalize_claude(raw)
        sid, ssrc = resolve_session(raw)
        record = handle_post_return(
            _active_state_dir(),
            tool_input,
            len(payload.tool_output),
            session_id=sid,
            session_source=ssrc,
        )
        _log_savings(record)
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
