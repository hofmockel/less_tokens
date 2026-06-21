#!/usr/bin/env python3
"""Codex PreToolUse hook: block repeated reads/searches already in context."""
from __future__ import annotations

import json
import os
import sys
import time
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
sys.path.insert(0, str(REPO / ".less_tokens" / "tools"))
sys.path.insert(0, str(REPO / ".claude" / "tools"))

try:
    from search_config import CONTEXT_CACHE_ENABLED, CONTEXT_CACHE_GREP_TTL, active_state_dir  # noqa: E402
except Exception:
    CONTEXT_CACHE_ENABLED = True
    CONTEXT_CACHE_GREP_TTL = 300

    def active_state_dir() -> Path:  # type: ignore[misc]
        return REPO / ".less_tokens" / "state"


def _cache_file() -> Path:
    return active_state_dir() / "context-cache.json"


def _load() -> dict:
    try:
        return json.loads(_cache_file().read_text())
    except Exception:
        return {}


def _save(state: dict) -> None:
    try:
        p = _cache_file()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(state))
    except Exception:
        pass


def _state(transcript_path: str | None) -> dict:
    if transcript_path is None:
        return {"session": None, "call": 0, "reads": {}, "greps": {}}
    state = _load()
    if state.get("session") != transcript_path:
        return {"session": transcript_path, "call": 0, "reads": {}, "greps": {}}
    return state


def _map_tool(raw: dict) -> tuple[str, dict]:
    tool = raw.get("tool_name", "")
    inp = raw.get("tool_input") or {}
    if tool == "mcp__filesystem__read_file":
        return "Read", {"file_path": inp.get("path", ""), "offset": inp.get("offset"), "limit": inp.get("limit")}
    if tool.startswith("mcp__filesystem__") and "search" in tool:
        return "Grep", inp
    return tool, inp


def _read_key(file_path: str, offset: object, limit: object) -> str:
    return f"{file_path}::{offset}::{limit}"


def main() -> int:
    if not CONTEXT_CACHE_ENABLED:
        return 0
    try:
        raw = json.loads(sys.stdin.read())
    except Exception:
        return 0
    tool, inp = _map_tool(raw)
    if tool not in {"Read", "Grep"}:
        return 0
    state = _state(raw.get("transcript_path"))
    state["call"] = state.get("call", 0) + 1

    if tool == "Read":
        fp = str(inp.get("file_path", ""))
        if not fp:
            _save(state)
            return 0
        key = _read_key(fp, inp.get("offset"), inp.get("limit"))
        entry = state.get("reads", {}).get(key)
        try:
            mtime = Path(fp).stat().st_mtime
        except OSError:
            mtime = 0.0
        if entry and mtime and entry.get("mtime") == mtime:
            age = int(time.time() - entry.get("ts", time.time()))
            label = Path(fp).name
            _save(state)
            print(
                f"context-cache: {label} already in context ({age}s ago) and unchanged. "
                "Skip this repeat read.",
                file=sys.stderr,
            )
            return 2
        state.setdefault("reads", {})[key] = {"mtime": mtime, "ts": time.time(), "call": state["call"]}
    else:
        key = ":::".join(str(inp.get(k, "")) for k in ("pattern", "path", "glob", "type", "query"))
        entry = state.get("greps", {}).get(key)
        if entry and time.time() - entry.get("ts", 0) <= CONTEXT_CACHE_GREP_TTL:
            _save(state)
            print("context-cache: search already ran recently; results are in context.", file=sys.stderr)
            return 2
        state.setdefault("greps", {})[key] = {"ts": time.time(), "call": state["call"]}

    _save(state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
