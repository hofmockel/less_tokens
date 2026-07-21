#!/usr/bin/env python3
"""Codex Stop/SubagentStop hook: continue overly verbose responses once."""
from __future__ import annotations

import sys

from _codex_runtime import bootstrap, load_json_stdin

bootstrap()

from response_budget import analyze  # noqa: E402

MAX_RESPONSE_WORDS = 600

try:
    from search_config import CAVEMAN_ENFORCE, MAX_RESPONSE_WORDS as _MRW  # noqa: E402
    MAX_RESPONSE_WORDS = _MRW
    if not CAVEMAN_ENFORCE:
        sys.exit(0)
except Exception:
    pass


def main() -> int:
    payload = load_json_stdin()
    if not payload:
        return 0
    if payload.get("hook_event_name") not in {"Stop", "SubagentStop"}:
        return 0
    if payload.get("stop_hook_active"):
        return 0
    response = payload.get("last_assistant_message", "") or ""
    if not isinstance(response, str):
        return 0
    violations = analyze(response, max_response_words=MAX_RESPONSE_WORDS, min_filler_hits=1)
    if not violations:
        return 0
    normalized = [
        v.replace("filler: ", "filler phrases detected: ", 1)
        for v in violations
    ]
    msg = "Response budget exceeded. Keep response concise. No filler. " + " | ".join(normalized)
    print(msg, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
