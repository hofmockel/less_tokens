#!/usr/bin/env python3
"""PreToolUse hook: enforce search-before-Read on indexed files (wired via .claude/settings.json)."""
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
    from agents.common.hooks.payload import normalize_claude  # type: ignore[import]
    from agents.common.hooks.search_first import check_search_first, is_indexed as _common_is_indexed, search_was_recent as _common_recent
except Exception:
    from payload import normalize_claude  # type: ignore[no-redef]
    from search_first import check_search_first, is_indexed as _common_is_indexed, search_was_recent as _common_recent  # type: ignore[no-redef]

_config: dict = {}


def _load_config() -> bool:
    try:
        import search_config  # noqa: E402
        _config["excluded_prefixes"] = search_config.EXCLUDED_DIR_PREFIXES
        _config["excluded_names"] = search_config.EXCLUDED_DIR_NAMES
        _config["root_globs"] = search_config.INDEXED_ROOT_GLOBS
        _config["dirs"] = search_config.INDEXED_SOURCE_DIRS
        _config["venv_py"] = search_config.VENV_PY
        _config["tool_prefix"] = ".claude/tools"
        _config["state_dir"] = search_config.active_state_dir()
        _config["state_file"] = _config["state_dir"] / "last-search"
        _config["window_seconds"] = search_config.WINDOW_SECONDS
    except Exception as e:
        print(f"search-first: could not load search_config ({e}); gate disabled", file=sys.stderr)
        return False
    try:
        from savings_log import append as _log  # noqa: PLC0415
        from savings_log import resolve_session  # noqa: PLC0415
        _config["log"] = _log
        _config["resolve_session"] = resolve_session
    except Exception:
        pass
    return True


def is_indexed(path: Path) -> bool:
    return _common_is_indexed(
        path,
        REPO,
        excluded_prefixes=_config.get("excluded_prefixes", ()),
        excluded_names=set(_config.get("excluded_names", ())),
        indexed_dirs=tuple(_config.get("dirs", ())),
        root_globs=tuple(_config.get("root_globs", ("*.md",))),
    )


def search_was_recent() -> bool:
    state_dir = _config.get("state_dir")
    if state_dir is None and _config.get("state_file") is not None:
        state_dir = Path(_config["state_file"]).parent
    return _common_recent(Path(state_dir), _config["window_seconds"]) if state_dir else False


def main() -> int:
    if not _load_config():
        return 0
    try:
        raw = json.load(sys.stdin)
    except Exception:
        return 0
    payload = normalize_claude(raw)
    code, stdout, stderr = check_search_first(payload, repo=REPO, state_dir=_config["state_dir"], config=_config)
    if code == 2:
        file_path = (payload.tool_input or {}).get("file_path", "")
        try:
            rel = Path(file_path).resolve().relative_to(REPO).as_posix()
            saved = Path(file_path).stat().st_size
        except Exception:
            rel = str(file_path)
            saved = 0
        _resolve = _config.get("resolve_session", lambda _r: ("local-session", "local"))
        sid, ssrc = _resolve(raw)
        _config.get("log", lambda _: None)({
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
        stderr = stderr.replace("Search-first rule:", "Search-first rule (CLAUDE.md):")
    if stdout:
        print(stdout)
    if stderr:
        print(stderr, file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
