#!/usr/bin/env python3
"""Codex Stop/SubagentStop hook: regenerate and report measured savings."""
from __future__ import annotations

import json
import sys

from _codex_runtime import bootstrap, load_json_stdin

bootstrap()


def main() -> int:
    payload = load_json_stdin()
    if not payload or payload.get("hook_event_name") not in {"Stop", "SubagentStop"}:
        return 0
    try:
        import stats  # type: ignore[import]
        from savings_log import _stats_disabled  # type: ignore[import]

        if _stats_disabled():
            return 0
        session = stats._load_records(all_time=False)
        stats._write_html_report(session, stats._load_records(all_time=True))
        if stats._measured_saved_chars(session) > 0:
            message = f"{stats._measured_oneliner(session)} - {stats._savings_link()}"
            print(json.dumps({"systemMessage": message}))
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
