#!/usr/bin/env python3
"""Codex PostToolUse hook: truncate oversized Bash and filesystem tool results."""
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
sys.path.insert(0, str(REPO / "agents" / "common" / "hooks"))
sys.path.insert(0, str(REPO / ".claude" / "tools"))

from payload import normalize_codex  # noqa: E402
from truncate_output import check_truncate_output  # noqa: E402

try:
    from search_config import (  # noqa: E402
        MAX_TOOL_OUTPUT_CHARS,
        MAX_GLOB_RESULTS,
        TOOL_OUTPUT_HEAD_LINES,
        TOOL_OUTPUT_TAIL_LINES,
    )
except Exception:
    MAX_TOOL_OUTPUT_CHARS = 4000
    MAX_GLOB_RESULTS = 100
    TOOL_OUTPUT_HEAD_LINES = 50
    TOOL_OUTPUT_TAIL_LINES = 20

raw = json.loads(sys.stdin.read())
payload = normalize_codex(raw)
code, stdout, stderr = check_truncate_output(
    payload,
    max_chars=MAX_TOOL_OUTPUT_CHARS,
    head_lines=TOOL_OUTPUT_HEAD_LINES,
    tail_lines=TOOL_OUTPUT_TAIL_LINES,
    max_glob_results=MAX_GLOB_RESULTS,
)
if stdout:
    print(stdout)
if stderr:
    print(stderr, file=sys.stderr)
sys.exit(code)
