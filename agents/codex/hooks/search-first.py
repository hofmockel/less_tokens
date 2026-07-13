#!/usr/bin/env python3
"""Codex PreToolUse hook: enforce search-before-read on indexed files.

Best-effort — unknown tool names pass silently (not a sandbox boundary).
"""
from __future__ import annotations

import sys
from pathlib import Path

from _codex_runtime import bootstrap, load_json_stdin, map_read, print_result

REPO = bootstrap()

from payload import normalize_codex  # noqa: E402
from search_first import check_search_first  # noqa: E402

try:
    from savings_log import append as _log_savings  # noqa: E402
    from savings_log import resolve_session  # noqa: E402
    from savings_log import STRATEGY_SEARCH_BLOCKED  # noqa: E402
except Exception:
    STRATEGY_SEARCH_BLOCKED = "search-blocked"

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

def main() -> int:
    raw = load_json_stdin(map_read)
    if not raw:
        return 0
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
            "strategy": STRATEGY_SEARCH_BLOCKED,
            "basis": "upper_bound",
            "kept_chars": 0,
            "elided_chars": saved,
            "content_kind": "source_file",
            "where": rel,
            "session_id": sid,
            "session_source": ssrc,
            "correlation_id": f"sf:{rel}",
        })
    return print_result(code, stdout, stderr)


if __name__ == "__main__":
    sys.exit(main())
