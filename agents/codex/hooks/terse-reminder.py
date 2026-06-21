#!/usr/bin/env python3
"""Codex PostToolUse hook: nudge for concise responses."""
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
sys.path[:0] = [
    str(REPO / "agents" / "common" / "hooks"),
    str(REPO / ".less_tokens" / "hooks"),
    str(REPO / ".less_tokens" / "tools"),
    str(REPO / ".claude" / "tools"),
]

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
    try:
        payload = json.loads(sys.stdin.read())
    except Exception:
        return 0
    if payload.get("stop_hook_active"):
        return 0
    response = payload.get("response", "") or ""
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
