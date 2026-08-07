#!/usr/bin/env python3
"""PreToolUse hook: block repeat Read/Grep calls already in context."""

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
    from agents.common.hooks.context_cache import (
        blocked_read_chars,
        check_context_cache,
        check_grep,
        check_read,
        get_state,
        grep_key,
        near_miss_signature,
        record_grep,
        record_near_miss,
        record_read,
        read_key,
        save_state,
    )
    from agents.common.hooks.payload import normalize_claude
except Exception:
    from context_cache import (  # type: ignore[no-redef]
        blocked_read_chars,
        check_context_cache,
        check_grep,
        check_read,
        get_state,
        grep_key,
        near_miss_signature,
        record_grep,
        record_near_miss,
        record_read,
        read_key,
        save_state,
    )
    from payload import normalize_claude  # type: ignore[no-redef]

try:
    from search_config import (
        CONTEXT_CACHE_ENABLED,
        CONTEXT_CACHE_GREP_TTL,
        active_state_dir as _active_state_dir,
    )  # noqa: E402
except Exception:
    CONTEXT_CACHE_ENABLED = True
    CONTEXT_CACHE_GREP_TTL = 300

    def _active_state_dir() -> Path:  # type: ignore[misc]
        return REPO / ".claude" / "state"


try:
    from savings_log import append as _log  # noqa: E402
    from savings_log import resolve_session  # noqa: E402
except Exception:

    def _log(_r: dict) -> None:
        pass

    def resolve_session(_raw: dict | None) -> tuple[str, str]:
        return "local-session", "local"


def _cache_file() -> Path:
    return _active_state_dir() / "context-cache.json"


def _load() -> dict:
    try:
        return json.loads(_cache_file().read_text())
    except Exception:
        return {}


def _save(state: dict) -> None:
    save_state(_active_state_dir(), state)


def _get_state(transcript_path: str | None) -> dict:
    return get_state(_active_state_dir(), transcript_path)


def _read_key(file_path: str, offset: object, limit: object) -> str:
    return read_key(file_path, offset, limit)


def _grep_key(inp: dict) -> str:
    return grep_key(inp)


def main() -> int:
    try:
        raw = json.load(sys.stdin)
    except Exception:
        return 0
    code, stdout, stderr = check_context_cache(
        normalize_claude(raw),
        state_dir=_active_state_dir(),
        enabled=CONTEXT_CACHE_ENABLED,
        grep_ttl=CONTEXT_CACHE_GREP_TTL,
        event_name=str(
            raw.get("hook_event_name") or raw.get("hookEventName") or "PreToolUse"
        ),
        log=_log,
        session=resolve_session(raw),
    )
    if stdout:
        print(stdout)
    if stderr:
        print(stderr, file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
