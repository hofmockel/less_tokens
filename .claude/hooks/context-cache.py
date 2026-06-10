#!/usr/bin/env python3
"""PreToolUse hook: block repeat Read/Grep calls whose content is already in context.

Keyed on (tool, args, file-mtime). On a repeat with unchanged inputs, exits 2
with "already in context (call #N) — unchanged since" instead of re-injecting
the payload.

Covers:
  Read  — key: (file_path, offset, limit) + mtime; invalidated when file changes
  Grep  — key: (pattern, path, glob, type); expires after CONTEXT_CACHE_GREP_TTL s

State lives in STATE_DIR/context-cache.json. Session boundary is detected via
transcript_path — a new path means a new session and the cache is cleared.

install.py wires this as PreToolUse on Read|Grep.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path


# ---------------------------------------------------------------------------
# Repo resolution (identical pattern to other hooks)
# ---------------------------------------------------------------------------

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
sys.path.insert(0, str(REPO / ".claude" / "tools"))

try:
    from search_config import active_state_dir as _active_state_dir, CONTEXT_CACHE_ENABLED, CONTEXT_CACHE_GREP_TTL
except Exception:
    def _active_state_dir() -> Path:  # type: ignore[misc]
        return REPO / ".claude" / "state"
    CONTEXT_CACHE_ENABLED = True
    CONTEXT_CACHE_GREP_TTL = 300

try:
    from savings_log import append as _log
except Exception:
    def _log(_r: dict) -> None: pass  # noqa: E301


def _cache_file() -> Path:
    return _active_state_dir() / "context-cache.json"


# ---------------------------------------------------------------------------
# State I/O
# ---------------------------------------------------------------------------

def _load() -> dict:
    try:
        return json.loads(_cache_file().read_text())
    except Exception:
        return {}


def _save(state: dict) -> None:
    try:
        cf = _cache_file()
        cf.parent.mkdir(parents=True, exist_ok=True)
        cf.write_text(json.dumps(state))
    except Exception:
        pass


def _get_state(transcript_path: str | None) -> dict:
    if transcript_path is None:
        return {"session": None, "call": 0, "reads": {}, "greps": {}}
    state = _load()
    if state.get("session") != transcript_path:
        return {"session": transcript_path, "call": 0, "reads": {}, "greps": {}}
    return state


# ---------------------------------------------------------------------------
# Read cache
# ---------------------------------------------------------------------------

def _read_key(file_path: str, offset: int | None, limit: int | None) -> str:
    return f"{file_path}::{offset}::{limit}"


def check_read(state: dict, file_path: str, offset: int | None, limit: int | None) -> str | None:
    """Return a block message, or None to allow."""
    key = _read_key(file_path, offset, limit)
    entry = state.get("reads", {}).get(key)
    if not entry:
        return None

    try:
        current_mtime = Path(file_path).stat().st_mtime
    except OSError:
        return None  # file gone — let Read surface the error

    if current_mtime != entry.get("mtime"):
        return None  # file changed — re-read is valid

    age = int(time.time() - entry["ts"])
    age_str = f"{age}s ago" if age < 120 else f"{age // 60}m ago"
    rel = Path(file_path).name
    call_n = entry["call"]
    return (
        f"context-cache: {rel} already in context (call #{call_n}, {age_str}) — "
        f"file unchanged. Skip this Read; content is still valid in context."
    )


def record_read(state: dict, file_path: str, offset: int | None, limit: int | None) -> None:
    try:
        mtime = Path(file_path).stat().st_mtime
    except OSError:
        mtime = 0.0
    key = _read_key(file_path, offset, limit)
    state.setdefault("reads", {})[key] = {
        "mtime": mtime,
        "ts": time.time(),
        "call": state.get("call", 0),
    }


# ---------------------------------------------------------------------------
# Grep cache
# ---------------------------------------------------------------------------

def _grep_key(inp: dict) -> str:
    return ":::".join([
        inp.get("pattern", ""),
        inp.get("path", ""),
        inp.get("glob", ""),
        inp.get("type", ""),
    ])


def check_grep(state: dict, inp: dict, ttl: int) -> str | None:
    key = _grep_key(inp)
    entry = state.get("greps", {}).get(key)
    if not entry:
        return None
    age = time.time() - entry["ts"]
    if age > ttl:
        return None  # expired
    call_n = entry["call"]
    age_str = f"{int(age)}s ago" if age < 120 else f"{int(age) // 60}m ago"
    pat = inp.get("pattern", "")[:50]
    return (
        f"context-cache: Grep '{pat}' already ran (call #{call_n}, {age_str}). "
        f"Results are in context — skip repeat."
    )


def record_grep(state: dict, inp: dict) -> None:
    key = _grep_key(inp)
    state.setdefault("greps", {})[key] = {
        "ts": time.time(),
        "call": state.get("call", 0),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    if not CONTEXT_CACHE_ENABLED:
        return 0

    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    tool = payload.get("tool_name")
    if tool not in ("Read", "Grep"):
        return 0

    transcript_path = payload.get("transcript_path")
    state = _get_state(transcript_path)
    state["call"] = state.get("call", 0) + 1
    inp = payload.get("tool_input", {}) or {}

    if tool == "Read":
        file_path = inp.get("file_path", "")
        if not file_path:
            _save(state)
            return 0
        offset = inp.get("offset") or None
        limit = inp.get("limit") or None

        msg = check_read(state, file_path, offset, limit)
        if msg:
            try:
                saved_chars = Path(file_path).stat().st_size
            except OSError:
                saved_chars = 0
            _log({"strategy": "context-cache-read", "file": file_path, "saved_chars": saved_chars})
            _save(state)
            print(msg, file=sys.stderr)
            return 2

        record_read(state, file_path, offset, limit)

    elif tool == "Grep":
        msg = check_grep(state, inp, CONTEXT_CACHE_GREP_TTL)
        if msg:
            _log({"strategy": "context-cache-grep", "pattern": inp.get("pattern", ""), "saved_chars": 0})
            _save(state)
            print(msg, file=sys.stderr)
            return 2
        record_grep(state, inp)

    _save(state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
