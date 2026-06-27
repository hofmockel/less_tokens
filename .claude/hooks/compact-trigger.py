#!/usr/bin/env python3
"""PostToolUse hook: nudge to compact when transcript grows large."""
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
    from agents.common.hooks.compact_trigger import check_compact_trigger, measure_compaction  # type: ignore[import]
    from agents.common.hooks.payload import normalize_claude
except Exception:
    from compact_trigger import check_compact_trigger, measure_compaction  # type: ignore[no-redef]
    from payload import normalize_claude  # type: ignore[no-redef]

try:
    from search_config import AGENT_MODEL, MAX_SESSION_CHARS, active_state_dir  # noqa: E402
    from model_profiles import scaled_compact_chars  # noqa: E402
    MAX_SESSION_CHARS = scaled_compact_chars(MAX_SESSION_CHARS, AGENT_MODEL)
except Exception:
    MAX_SESSION_CHARS = 500_000

    def active_state_dir() -> Path:  # type: ignore[misc]
        return REPO / ".claude" / "state"

try:
    from savings_log import append as _log_savings  # noqa: E402
    from savings_log import resolve_session  # noqa: E402
except Exception:
    def _log_savings(_r: dict) -> None:
        pass

    def resolve_session(_raw: dict | None) -> tuple[str, str]:
        return "local-session", "local"

STATE_FILE = active_state_dir() / "compact-trigger-last"


def main() -> int:
    try:
        raw = json.load(sys.stdin)
    except Exception:
        return 0
    payload = normalize_claude(raw)
    # Record measured compaction savings when the transcript has shrunk.
    try:
        measure_compaction(
            payload,
            state_dir=active_state_dir(),
            max_session_chars=MAX_SESSION_CHARS,
            log=_log_savings,
            session=resolve_session(raw),
        )
    except Exception:
        pass
    code, stdout, stderr = check_compact_trigger(
        payload,
        state_dir=active_state_dir(),
        max_session_chars=MAX_SESSION_CHARS,
        state_file=STATE_FILE,
        message=(
            "Transcript is {size:,} chars (threshold {threshold:,}). "
            "Run /compact or start a fresh Claude session before more work."
        ),
    )
    if stdout:
        print(stdout)
    if stderr:
        print(stderr, file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
