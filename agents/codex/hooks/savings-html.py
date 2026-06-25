#!/usr/bin/env python3
"""Codex PostToolUse hook: regenerate .less_tokens/state/savings.html."""
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
os.environ.setdefault("LESS_TOKENS_AGENT", "codex")
sys.path.insert(0, str(REPO / ".less_tokens" / "tools"))
sys.path.insert(0, str(REPO / ".claude" / "tools"))


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
        if stats._measured_saved_chars(session) > 0:
            print(f"{stats._measured_oneliner(session)} - {stats._savings_link()}")
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
