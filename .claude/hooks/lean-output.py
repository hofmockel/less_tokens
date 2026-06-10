#!/usr/bin/env python3
"""PostToolUse hook: pipe Bash output through signal-only parsers.

Detects pytest, ruff, eslint, and git in the Bash command and routes output
through parse.py. Emits hookSpecificOutput only when the result is shorter,
so the context cost is the signal, not the noise.
install.py wires this as PostToolUse on Bash.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
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
    return Path.cwd().resolve()


REPO = _resolve_repo()
_TOOLS = REPO / ".claude" / "tools"


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


def _venv_py() -> Path | None:
    try:
        sys.path.insert(0, str(_TOOLS))
        import search_config  # noqa: E402
        p = Path(search_config.VENV_PY)
        return p if p.exists() else None
    except Exception:
        return None


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    cmd = (payload.get("tool_input") or {}).get("command", "")
    tool = _detect_tool(cmd)
    if not tool:
        sys.exit(0)

    raw = payload.get("tool_response") or payload.get("tool_result") or ""
    if not raw:
        sys.exit(0)

    venv_py = _venv_py()
    parse_py = _TOOLS / "parse.py"
    if not parse_py.exists() or not venv_py:
        sys.exit(0)

    try:
        r = subprocess.run(
            [str(venv_py), str(parse_py), tool],
            input=raw, capture_output=True, text=True, timeout=10,
        )
        parsed = r.stdout
    except Exception:
        sys.exit(0)

    if not parsed or len(parsed) >= len(raw) * 0.9:
        sys.exit(0)

    saved = len(raw) - len(parsed)
    print(json.dumps({"hookSpecificOutput":
        f"[lean-output:{tool}] {saved} chars trimmed\n{parsed}"}))


if __name__ == "__main__":
    main()
