#!/usr/bin/env python3
"""Stop hook: regenerate state/savings.html so the page is always current.

Runs after every turn, reads the local savings log, and rewrites the
self-contained HTML report. Fully
failure-safe and silent: any error (no log yet, import failure, write error)
returns 0 so it never blocks the turn or nags the transcript.
"""

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
    return Path(__file__).resolve().parent.parent.parent


REPO = _resolve_repo()
sys.path[:0] = [str(REPO / ".claude" / "tools")]


def main() -> int:
    try:
        json.load(sys.stdin)
    except Exception:
        pass
    try:
        import stats  # type: ignore[import]
        from savings_log import _stats_disabled  # type: ignore[import]

        if _stats_disabled():
            return 0
        session = stats._load_records(all_time=False)
        stats._write_html_report(session, stats._load_records(all_time=True))
        # Phase 5 surfacing: a measured one-liner + file:// link the user can
        # click through from the transcript. Quiet when nothing was saved yet.
        if stats._measured_saved_chars(session) > 0:
            print(f"{stats._measured_oneliner(session)} — {stats._savings_link()}")
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
