#!/usr/bin/env python3
"""Codex PostToolUse hook: nudge to start a fresh session when transcript grows large."""
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
from compact_trigger import check_compact_trigger, measure_compaction  # noqa: E402

try:
    from savings_log import append as _log_savings  # noqa: E402
    from savings_log import resolve_session  # noqa: E402
except Exception:
    def _log_savings(_r: dict) -> None:
        pass

    def resolve_session(_raw: dict | None) -> tuple[str, str]:
        return "local-session", "local"

try:
    from search_config import MAX_SESSION_CHARS, active_state_dir  # noqa: E402
    state_dir = active_state_dir()
except Exception:
    MAX_SESSION_CHARS = 500_000
    state_dir = REPO / ".less_tokens" / "state"

raw = json.loads(sys.stdin.read())
payload = normalize_codex(raw)
try:
    measure_compaction(
        payload,
        state_dir=state_dir,
        max_session_chars=MAX_SESSION_CHARS,
        log=_log_savings,
        session=resolve_session(raw),
    )
except Exception:
    pass
code, stdout, stderr = check_compact_trigger(
    payload,
    state_dir=state_dir,
    max_session_chars=MAX_SESSION_CHARS,
    message=(
        "Session transcript is now {size:,} chars (threshold {threshold:,}). "
        "Start a fresh or compacted Codex session if context pressure is high."
    ),
)
if stdout:
    print(stdout)
if stderr:
    print(stderr, file=sys.stderr)
sys.exit(code)
