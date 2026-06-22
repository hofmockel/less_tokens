#!/usr/bin/env python3
"""Stop hook: enforce terse output on Claude's actual response."""
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
    curr = Path.cwd().resolve()
    for _ in range(10):
        if (curr / ".git").exists() or (curr / "CLAUDE.md").exists():
            return curr
        if curr == curr.parent:
            break
        curr = curr.parent
    return Path(__file__).resolve().parent.parent.parent


REPO = _resolve_repo()
sys.path[:0] = [
    str(REPO),
    str(REPO / "agents" / "common" / "hooks"),
    str(REPO / ".claude" / "hooks" / "common"),
    str(REPO / ".claude" / "tools"),
]

try:
    from agents.common.hooks.response_budget import VERBOSE_PATTERNS, analyze as _analyze, last_assistant_text  # type: ignore[import]
except Exception:
    from response_budget import VERBOSE_PATTERNS, analyze as _analyze, last_assistant_text  # type: ignore[no-redef]

try:
    from search_config import CAVEMAN_ENFORCE, MAX_RESPONSE_WORDS  # noqa: E402
except Exception:
    CAVEMAN_ENFORCE = True
    MAX_RESPONSE_WORDS = 600


def analyze(text: str) -> list[str]:
    return _analyze(text, max_response_words=MAX_RESPONSE_WORDS, min_filler_hits=1)


def main() -> int:
    if not CAVEMAN_ENFORCE:
        return 0
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if payload.get("stop_hook_active"):
        return 0
    problems = analyze(last_assistant_text(payload.get("transcript_path", "")))
    if problems:
        print(
            "Caveman mode: revise last response — " + "; ".join(problems)
            + ". Cut filler and padding; short sentences; stop when done.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
