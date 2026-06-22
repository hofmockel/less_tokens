#!/usr/bin/env python3
"""Codex hook: record v2 budget telemetry without changing tool outcomes."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _resolve_repo() -> Path:
    if os.environ.get("LESS_TOKENS_REPO"):
        return Path(os.environ["LESS_TOKENS_REPO"]).resolve()
    curr = Path(__file__).resolve().parent
    for _ in range(8):
        if (curr / ".git").exists() or (curr / "AGENTS.md").exists():
            return curr
        curr = curr.parent
    return Path.cwd().resolve()


REPO = _resolve_repo()
sys.path[:0] = [
    str(REPO),
    str(REPO / ".less_tokens" / "hooks"),
    str(REPO / "agents" / "common" / "hooks"),
]

from budget_observer import budget_hook_outcome  # noqa: E402

try:
    from agents.common.budget.advice import claude_hook_output  # noqa: E402
except Exception:
    from budget.advice import claude_hook_output  # type: ignore[no-redef]  # noqa: E402


def main() -> int:
    try:
        raw = json.loads(sys.stdin.read() or "{}")
    except Exception:
        return 0
    if raw.get("tool_name") == "mcp__filesystem__read_file":
        raw["tool_name"] = "Read"
        raw.setdefault("tool_input", {})["file_path"] = raw.get("tool_input", {}).get("path", "")
    outcome = budget_hook_outcome(raw, repo=REPO, agent="codex")
    if not outcome:
        return 0
    if outcome.message:
        if outcome.stream == "stderr":
            print(outcome.message, file=sys.stderr)
        else:
            print(claude_hook_output(outcome.message))
    return outcome.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
