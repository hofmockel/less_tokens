#!/usr/bin/env python3
"""Codex PreToolUse hook: redirect whole-file reads to last-search slices."""
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
from auto_slice import check_auto_slice  # noqa: E402

try:
    from search_config import WINDOW_SECONDS, active_state_dir  # noqa: E402
    state_dir = active_state_dir()
except Exception:
    WINDOW_SECONDS = 300
    state_dir = REPO / ".less_tokens" / "state"


def _map_read(raw: dict) -> dict:
    if raw.get("tool_name") == "mcp__filesystem__read_file":
        inp = raw.setdefault("tool_input", {})
        raw["tool_name"] = "Read"
        inp["file_path"] = inp.get("path", "")
    return raw


def main() -> int:
    try:
        raw = _map_read(json.loads(sys.stdin.read()))
    except Exception:
        return 0
    payload = normalize_codex(raw)
    code, stdout, stderr = check_auto_slice(
        payload,
        state_dir=state_dir,
        window_seconds=WINDOW_SECONDS,
        read_example="Read file_path={file_path!r} offset={start} limit={limit}",
    )
    if stdout:
        print(stdout)
    if stderr:
        print(stderr, file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
