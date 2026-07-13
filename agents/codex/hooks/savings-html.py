#!/usr/bin/env python3
"""Codex PostToolUse hook: regenerate .less_tokens/state/savings.html."""
from __future__ import annotations

import sys

from _codex_runtime import bootstrap, load_json_stdin

bootstrap()


def main() -> int:
    load_json_stdin()
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
