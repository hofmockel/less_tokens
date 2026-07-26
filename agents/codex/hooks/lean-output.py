#!/usr/bin/env python3
"""Codex PostToolUse hook: parse noisy Bash output into signal-only summaries."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from _codex_runtime import bootstrap, load_json_stdin, venv_python

REPO = bootstrap()
TOOLS = REPO / ".less_tokens" / "tools"
if not (TOOLS / "parse.py").exists():
    TOOLS = REPO / ".claude" / "tools"


def _detect_tool(cmd: str) -> str | None:
    if re.search(r"\bpytest\b", cmd):
        return "pytest"
    if re.search(r"\bruff\b", cmd):
        return "ruff"
    if re.search(r"\beslint\b", cmd):
        return "eslint"
    if re.search(r"\bgit\s+(status|diff|log|show)\b", cmd):
        return "git"
    return None


def _python() -> Path:
    return venv_python(REPO)


def main() -> int:
    payload = load_json_stdin()
    if not payload:
        return 0
    if payload.get("tool_name") != "Bash":
        return 0
    cmd = (payload.get("tool_input") or {}).get("command", "")
    parser = _detect_tool(cmd)
    if not parser:
        return 0
    raw = payload.get("tool_response") or payload.get("tool_result") or ""
    if not raw:
        return 0
    parse_py = TOOLS / "parse.py"
    if not parse_py.exists():
        return 0
    try:
        result = subprocess.run(
            [str(_python()), str(parse_py), parser],
            input=str(raw),
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:
        return 0
    parsed = result.stdout
    if not parsed or len(parsed) >= len(str(raw)) * 0.9:
        return 0
    saved = len(str(raw)) - len(parsed)
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": f"[lean-output:{parser}] {saved} chars trimmed\n{parsed}",
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
