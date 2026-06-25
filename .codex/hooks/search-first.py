#!/usr/bin/env python3
"""Codex PreToolUse hook: enforce search-before-read on indexed files.

Best-effort — unknown tool names pass silently (not a sandbox boundary).
"""
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
sys.path.insert(0, str(REPO / ".less_tokens" / "hooks"))
sys.path.insert(0, str(REPO / "agents" / "common" / "hooks"))
sys.path.insert(0, str(REPO / ".less_tokens" / "tools"))
sys.path.insert(0, str(REPO / ".claude" / "tools"))

from payload import normalize_codex  # noqa: E402
from search_first import check_search_first  # noqa: E402

try:
    from savings_log import append as _log_savings  # noqa: E402
    from savings_log import resolve_session  # noqa: E402
except Exception:
    def _log_savings(_r: dict) -> None:
        pass

    def resolve_session(_raw: dict | None) -> tuple[str, str]:
        return "local-session", "local"

try:
    from search_config import (  # noqa: E402
        active_state_dir,
        EXCLUDED_DIR_NAMES,
        EXCLUDED_DIR_PREFIXES,
        INDEXED_ROOT_GLOBS,
        INDEXED_SOURCE_DIRS,
        WINDOW_SECONDS,
        VENV_PY,
    )
    config = {
        "excluded_prefixes": EXCLUDED_DIR_PREFIXES,
        "excluded_names": EXCLUDED_DIR_NAMES,
        "dirs": INDEXED_SOURCE_DIRS,
        "root_globs": INDEXED_ROOT_GLOBS,
        "window_seconds": WINDOW_SECONDS,
        "venv_py": ".less_tokens/bin/python",
        "tool_prefix": ".less_tokens/tools",
    }
    state_dir = active_state_dir()
except Exception:
    config = {"window_seconds": 300, "venv_py": "python3"}
    state_dir = REPO / ".less_tokens" / "state"

# Map Codex filesystem tool to the Read equivalent
raw = json.loads(sys.stdin.read())
if raw.get("tool_name") == "mcp__filesystem__read_file":
    raw["tool_name"] = "Read"
    raw.setdefault("tool_input", {})["file_path"] = (
        raw.get("tool_input", {}).get("path", "")
    )

payload = normalize_codex(raw)
code, stdout, stderr = check_search_first(payload, repo=REPO, state_dir=state_dir, config=config)
if code == 2:
    file_path = (payload.tool_input or {}).get("file_path", "")
    try:
        rel = Path(file_path).resolve().relative_to(REPO).as_posix()
        saved = Path(file_path).stat().st_size
    except Exception:
        rel = str(file_path)
        saved = 0
    sid, ssrc = resolve_session(raw)
    _log_savings({
        "strategy": "search-blocked",
        "basis": "upper_bound",
        "kept_chars": 0,
        "elided_chars": saved,
        "content_kind": "source_file",
        "where": rel,
        "session_id": sid,
        "session_source": ssrc,
        "correlation_id": f"sf:{rel}",
    })
if stdout:
    print(stdout)
if stderr:
    print(stderr, file=sys.stderr)
sys.exit(code)
