"""Shared context-cache logic for repeated reads and searches."""
from __future__ import annotations

import json
import time
from pathlib import Path

try:
    from .payload import HookPayload
except ImportError:
    from payload import HookPayload  # type: ignore[no-redef]


def cache_file(state_dir: Path) -> Path:
    return state_dir / "context-cache.json"


def load_state(state_dir: Path) -> dict:
    try:
        return json.loads(cache_file(state_dir).read_text())
    except Exception:
        return {}


def save_state(state_dir: Path, state: dict) -> None:
    try:
        path = cache_file(state_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state))
    except Exception:
        pass


def get_state(state_dir: Path, transcript_path: str | None) -> dict:
    if transcript_path is None:
        return {"session": None, "call": 0, "reads": {}, "greps": {}}
    state = load_state(state_dir)
    if state.get("session") != transcript_path:
        return {"session": transcript_path, "call": 0, "reads": {}, "greps": {}}
    return state


def read_key(file_path: str, offset: object, limit: object) -> str:
    return f"{file_path}::{offset}::{limit}"


def check_read(state: dict, file_path: str, offset: object, limit: object) -> str | None:
    key = read_key(file_path, offset, limit)
    entry = state.get("reads", {}).get(key)
    if not entry:
        return None
    try:
        current_mtime = Path(file_path).stat().st_mtime
    except OSError:
        return None
    if current_mtime != entry.get("mtime"):
        return None
    age = int(time.time() - entry["ts"])
    age_str = f"{age}s ago" if age < 120 else f"{age // 60}m ago"
    return (
        f"context-cache: {Path(file_path).name} already in context "
        f"(call #{entry['call']}, {age_str}) — file unchanged. "
        "Skip this Read; content is still valid in context."
    )


def record_read(state: dict, file_path: str, offset: object, limit: object) -> None:
    try:
        mtime = Path(file_path).stat().st_mtime
    except OSError:
        mtime = 0.0
    state.setdefault("reads", {})[read_key(file_path, offset, limit)] = {
        "mtime": mtime,
        "ts": time.time(),
        "call": state.get("call", 0),
    }


def grep_key(inp: dict) -> str:
    return ":::".join(str(inp.get(k, "")) for k in ("pattern", "path", "glob", "type", "query"))


def check_grep(state: dict, inp: dict, ttl: int) -> str | None:
    key = grep_key(inp)
    entry = state.get("greps", {}).get(key)
    if not entry:
        return None
    age = time.time() - entry["ts"]
    if age > ttl:
        return None
    age_str = f"{int(age)}s ago" if age < 120 else f"{int(age) // 60}m ago"
    pat = str(inp.get("pattern") or inp.get("query") or "")[:50]
    return (
        f"context-cache: Grep '{pat}' already ran "
        f"(call #{entry['call']}, {age_str}). Results are in context — skip repeat."
    )


def record_grep(state: dict, inp: dict) -> None:
    state.setdefault("greps", {})[grep_key(inp)] = {
        "ts": time.time(),
        "call": state.get("call", 0),
    }


def check_context_cache(
    payload: HookPayload,
    *,
    state_dir: Path,
    enabled: bool,
    grep_ttl: int,
    log=None,
) -> tuple[int, str, str]:
    if not enabled:
        return 0, "", ""
    if payload.tool_name not in {"Read", "Grep"}:
        return 0, "", ""

    state = get_state(
        state_dir,
        str(payload.transcript_path) if payload.transcript_path is not None else None,
    )
    state["call"] = state.get("call", 0) + 1
    inp = payload.tool_input or {}

    if payload.tool_name == "Read":
        file_path = str(inp.get("file_path", ""))
        if not file_path:
            save_state(state_dir, state)
            return 0, "", ""
        offset = inp.get("offset") or None
        limit = inp.get("limit") or None
        msg = check_read(state, file_path, offset, limit)
        if msg:
            if log:
                try:
                    saved_chars = Path(file_path).stat().st_size
                except OSError:
                    saved_chars = 0
                log({"strategy": "context-cache-read", "file": file_path, "saved_chars": saved_chars})
            save_state(state_dir, state)
            return 2, "", msg
        record_read(state, file_path, offset, limit)
    else:
        msg = check_grep(state, inp, grep_ttl)
        if msg:
            if log:
                log({"strategy": "context-cache-grep", "pattern": inp.get("pattern", ""), "saved_chars": 0})
            save_state(state_dir, state)
            return 2, "", msg
        record_grep(state, inp)

    save_state(state_dir, state)
    return 0, "", ""
