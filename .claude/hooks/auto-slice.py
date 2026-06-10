#!/usr/bin/env python3
"""PreToolUse hook: turn a whole-file Read of a search hit into a slice (S9).

After a search, `search.py` records each hit's matched line range in
`STATE_DIR/last-search.json`. When Claude then Reads one of those files with no
`offset`, this computes the slice and blocks with the exact targeted
`Read(offset, limit)` — the model obeys a computed instruction instead of
loading the whole file. Pass any `offset` (e.g. 1) to read the whole file anyway.

Only fires when the file is in the last search's hits and that search is recent
(within WINDOW_SECONDS). Otherwise passes.
install.py wires this as PreToolUse on Read.
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
    from search_config import active_state_dir, WINDOW_SECONDS
except Exception:
    def active_state_dir() -> Path:  # type: ignore[misc]
        return REPO / ".claude" / "state"
    WINDOW_SECONDS = 300

RANGES_FILE = active_state_dir() / "last-search.json"


def _ranges_for(file_path: str) -> list[list[int]]:
    """Matched line ranges for file_path from the last (recent) search."""
    try:
        if (time.time() - RANGES_FILE.stat().st_mtime) > WINDOW_SECONDS:
            return []
        data = json.loads(RANGES_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    p = Path(file_path)
    for key, spans in data.items():
        kp = Path(key)
        if kp == p or kp.name == p.name or str(p).endswith(str(kp)):
            return spans or []
    return []


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if payload.get("tool_name") != "Read":
        return 0
    inp = payload.get("tool_input", {})
    if inp.get("offset"):  # deliberate slice / override — allow
        return 0
    fp = inp.get("file_path", "")
    if not fp:
        return 0
    spans = _ranges_for(fp)
    if not spans:
        return 0

    # Best hit is first (search results are score-ranked).
    start, end = spans[0]
    limit = max(1, end - start + 1)
    extra = (f" (plus {len(spans) - 1} more matched range(s) in this file)"
             if len(spans) > 1 else "")
    print(
        f"Auto-slice (S9): your last search matched {Path(fp).name} at lines "
        f"{start}-{end}{extra}. Read only that slice:\n"
        f"  Read(file_path={fp!r}, offset={start}, limit={limit})\n"
        f"To read the whole file anyway, pass offset=1.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
