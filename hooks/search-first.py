#!/usr/bin/env python3
"""PreToolUse hook: enforce search-before-Read on indexed files.

Exits 2 with a reminder when an indexed file is Read without a recent search.
Gate clears for WINDOW_SECONDS after any search; configure in search_config.py.
install.py wires this into .claude/settings.json automatically.
"""
from __future__ import annotations

import json
import sys
import os
import time
from pathlib import Path

def _resolve_repo() -> Path:
    if os.environ.get("LESS_TOKENS_REPO"):
        return Path(os.environ["LESS_TOKENS_REPO"]).resolve()
    curr = Path(__file__).resolve().parent
    for _ in range(4):
        if (curr / "CLAUDE.md").exists() or (curr / ".git").exists():
            return curr
        curr = curr.parent
    return Path(__file__).resolve().parent.parent.parent


REPO = _resolve_repo()


_config: dict = {}


def _load_config() -> bool:
    """Load search_config into _config. Returns False (and warns) on failure."""
    try:
        sys.path.insert(0, str(REPO / ".claude" / "tools"))
        import search_config  # noqa: E402
        _config["excluded_prefixes"] = search_config.EXCLUDED_DIR_PREFIXES
        _config["excluded_names"] = search_config.EXCLUDED_DIR_NAMES
        _config["root_globs"] = search_config.INDEXED_ROOT_GLOBS
        _config["dirs"] = search_config.INDEXED_SOURCE_DIRS
        _config["venv_py"] = search_config.VENV_PY
        _config["state_file"] = search_config.STATE_DIR / "last-search"
        _config["window_seconds"] = search_config.WINDOW_SECONDS
        from savings_log import append as _log  # noqa: PLC0415
        _config["log"] = _log
        return True
    except Exception as e:
        print(f"search-first: could not load search_config ({e}); gate disabled", file=sys.stderr)
        return False


def is_indexed(path: Path) -> bool:
    try:
        rel = path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return False
    excluded_prefixes = _config.get("excluded_prefixes", [])
    excluded_names = _config.get("excluded_names", [])
    dirs = _config.get("dirs", [])

    parts = set(Path(rel).parts)
    if bool(parts & set(excluded_names)):
        return False
    if any(rel.startswith(p) for p in excluded_prefixes):
        return False

    if "/" not in rel:
        return rel.endswith((".md", ".py", ".sql"))
    if any(rel.startswith(d) for d in dirs):
        return rel.endswith((".py", ".sql"))
    return False


def search_was_recent() -> bool:
    state_file = _config.get("state_file")
    if not state_file:
        return False
    try:
        mtime = state_file.stat().st_mtime
    except OSError:
        return False
    return (time.time() - mtime) < _config.get("window_seconds", 300)


def main() -> int:
    if not _load_config():
        return 0  # degrade gracefully; don't block Reads

    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    if payload.get("tool_name") != "Read":
        return 0
    file_path = payload.get("tool_input", {}).get("file_path", "")
    if not file_path:
        return 0

    p = Path(file_path)
    if not is_indexed(p):
        return 0
    if search_was_recent():
        return 0

    venv_py = _config.get("venv_py", "python3")
    rel = p.resolve().relative_to(REPO).as_posix()
    try:
        file_chars = p.stat().st_size
    except OSError:
        file_chars = 0
    _config.get("log", lambda _: None)(
        {"strategy": "search-blocked", "file": rel, "saved_chars": file_chars}
    )
    msg = (
        f"Search-first rule (CLAUDE.md): {rel} is indexed.\n"
        f"Run vector search before Read:\n"
        f"  {venv_py} .claude/tools/search.py \"<your query>\"\n"
        f"After a search, Reads on indexed files are allowed for "
        f"{_config.get('window_seconds', 300)}s. If you need to edit this file, search first to "
        f"satisfy the gate, then Read + Edit normally."
    )
    print(msg, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
