#!/usr/bin/env python3
"""PreToolUse hook: block verify re-Read of recently edited files.

post-edit-diff.py (PostToolUse on Edit|Write) emits a diff and records the
edited path + timestamp to STATE_DIR/last-edit.json.  This hook checks that
record and blocks a whole-file Read of the same path within
LAST_EDIT_WINDOW_SECONDS — the diff is already in context; re-reading burns
tokens without adding information.

A Read with an explicit offset (deliberate slice) is always allowed.
install.py wires this as PreToolUse on Read alongside read-guard.py.
"""
from __future__ import annotations

import json
import os
import sys
import time
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
sys.path.insert(0, str(REPO / ".claude" / "tools"))

try:
    from search_config import LAST_EDIT_WINDOW_SECONDS, active_state_dir as _active_state_dir
except Exception:
    LAST_EDIT_WINDOW_SECONDS = 120
    def _active_state_dir() -> Path:  # type: ignore[misc]
        return REPO / ".claude" / "state"


def _load_edits() -> dict[str, float]:
    try:
        return json.loads((_active_state_dir() / "last-edit.json").read_text())
    except Exception:
        return {}


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    if payload.get("tool_name") != "Read":
        return 0

    inp = payload.get("tool_input", {})
    if inp.get("offset") is not None:  # deliberate slice — always allow
        return 0

    file_path = inp.get("file_path", "")
    if not file_path:
        return 0

    edits = _load_edits()
    if not edits:
        return 0

    abs_path = str(Path(file_path).resolve())
    edit_ts = edits.get(abs_path)
    if edit_ts is None:
        return 0

    age = time.time() - edit_ts
    if age > LAST_EDIT_WINDOW_SECONDS:
        return 0

    label = Path(file_path).name
    print(
        f"read-after-edit: {label} was edited {age:.0f}s ago — diff already in context. "
        f"Skip re-Read; use the diff or Read with offset+limit if you need a specific slice.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
