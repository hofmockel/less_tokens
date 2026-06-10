#!/usr/bin/env python3
"""Codex PostToolUse hook: nudge for concise responses (Codex-appropriate caveman equivalent)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_FILLER_PHRASES = [
    "certainly", "of course", "i'd be happy to", "great question",
    "i apologize", "i'm sorry", "absolutely", "no problem",
    "as an ai", "as a language model",
    "i hope this helps", "feel free to",
    "please note that", "it's worth noting",
    "in conclusion", "to summarize",
]

MIN_FILLER_HITS = 2
MAX_RESPONSE_WORDS = 600


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
sys.path.insert(0, str(REPO / ".claude" / "tools"))

try:
    from search_config import active_state_dir, CAVEMAN_ENFORCE, MAX_RESPONSE_WORDS as _MRW  # noqa: E402
    MAX_RESPONSE_WORDS = _MRW
    state_dir = active_state_dir()
    if not CAVEMAN_ENFORCE:
        sys.exit(0)
except Exception:
    state_dir = REPO / ".less_tokens" / "state"


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read())
    except Exception:
        return 0

    response = payload.get("response", "") or ""
    if not isinstance(response, str):
        return 0

    lower = response.lower()
    hits = [p for p in _FILLER_PHRASES if p in lower]
    words = len(response.split())

    violations = []
    if len(hits) >= MIN_FILLER_HITS:
        violations.append(f"filler phrases detected: {', '.join(hits[:3])}")
    if MAX_RESPONSE_WORDS and words > MAX_RESPONSE_WORDS:
        violations.append(f"response too long ({words} words, limit {MAX_RESPONSE_WORDS})")

    if not violations:
        return 0

    msg = "Response budget exceeded. Keep response concise. No filler. " + " | ".join(violations)
    print(msg, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
