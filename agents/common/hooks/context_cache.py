"""Shared context-cache logic for repeated reads and searches."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

try:
    from .payload import HookPayload
except ImportError:
    from payload import HookPayload  # type: ignore[no-redef]

# Best-effort import of the canonical strategy keys. This module is agent-neutral
# (shared by Claude and Codex hooks) and must not hard-depend on the Claude-only
# .claude/tools/savings_log path, so fall back to the literals if it isn't on
# sys.path — the literals must stay in sync with savings_log's STRATEGY_* names.
try:
    from savings_log import (  # noqa: PLC0415
        STRATEGY_CONTEXT_CACHE_BASH,
        STRATEGY_CONTEXT_CACHE_GREP,
        STRATEGY_CONTEXT_CACHE_READ,
    )
except Exception:
    STRATEGY_CONTEXT_CACHE_BASH = "context-cache-bash"
    STRATEGY_CONTEXT_CACHE_GREP = "context-cache-grep"
    STRATEGY_CONTEXT_CACHE_READ = "context-cache-read"


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
        return {"session": None, "call": 0, "reads": {}, "greps": {}, "bash": {}}
    state = load_state(state_dir)
    if state.get("session") != transcript_path:
        return {"session": transcript_path, "call": 0, "reads": {}, "greps": {}, "bash": {}}
    state.setdefault("bash", {})
    return state


def read_key(file_path: str, offset: object, limit: object) -> str:
    return f"{file_path}::{offset}::{limit}"


def blocked_read_chars(file_path: str, offset: object, limit: object) -> int:
    """Chars the blocked Read would have re-injected into context.

    The cache key is ``file::offset::limit``, so a block always repeats the exact
    same slice. A full read (no offset/limit) re-injects the whole file, so its byte
    size is exact. A partial read re-injects only its line slice, so crediting the
    full file size would overstate the saving — measure the slice instead (Read's
    ``offset`` is a 1-based line; ``limit`` is a line count). Best-effort: any read
    error falls back to the full size. Only runs on the rare block path, not per call.
    """
    try:
        size = Path(file_path).stat().st_size
    except OSError:
        return 0
    if not offset and not limit:
        return size
    try:
        start = (int(offset) - 1) if offset else 0
        start = max(0, start)
        end = (start + int(limit)) if limit else None
        total = 0
        with Path(file_path).open(encoding="utf-8", errors="replace") as fh:
            for idx, line in enumerate(fh):
                if idx < start:
                    continue
                if end is not None and idx >= end:
                    break
                total += len(line)
        return total
    except (OSError, ValueError):
        return size


def check_read(state: dict, file_path: str, offset: object, limit: object) -> str | None:
    key = read_key(file_path, offset, limit)
    entry = state.get("reads", {}).get(key)
    if not entry:
        return None
    try:
        st = Path(file_path).stat()
    except OSError:
        return None
    if st.st_mtime != entry.get("mtime") or st.st_size != entry.get("size"):
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
        st = Path(file_path).stat()
        mtime, size = st.st_mtime, st.st_size
    except OSError:
        mtime, size = 0.0, -1
    state.setdefault("reads", {})[read_key(file_path, offset, limit)] = {
        "mtime": mtime,
        "size": size,
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


def bash_command(inp: dict) -> str:
    return str(inp.get("command", "")).strip()


def cacheable_bash_command(command: str) -> bool:
    if not command:
        return False
    return bool(
        command == "pwd"
        or re.fullmatch(r"git\s+status\b.*", command)
        or re.fullmatch(r"rg\b.*", command)
        or re.fullmatch(r"(?:python(?:3)?\s+-m\s+)?pytest\b.*", command)
    )


def check_bash(state: dict, inp: dict, ttl: int) -> tuple[str | None, int]:
    command = bash_command(inp)
    if not cacheable_bash_command(command):
        return None, 0
    entry = state.get("bash", {}).get(command)
    if not entry:
        return None, 0
    age = time.time() - entry["ts"]
    if age > ttl:
        return None, 0
    age_str = f"{int(age)}s ago" if age < 120 else f"{int(age) // 60}m ago"
    saved = int(entry.get("output_chars", 0) or 0)
    return (
        f"context-cache: Bash `{command}` already ran "
        f"(call #{entry['call']}, {age_str}). Output is already in context — skip repeat.",
        saved,
    )


def record_bash(state: dict, inp: dict, output_chars: int) -> None:
    command = bash_command(inp)
    if not cacheable_bash_command(command):
        return
    state.setdefault("bash", {})[command] = {
        "ts": time.time(),
        "call": state.get("call", 0),
        "output_chars": max(0, output_chars),
    }


def near_miss_signature(command: str) -> str:
    """Coarse grouping key for near-miss analysis: base command only, so
    `pytest -v foo.py` and `pytest bar.py` share a signature even though
    the exact-string cache in check_bash/record_bash treats them as unrelated."""
    parts = command.split()
    return parts[0] if parts else ""


def record_near_miss(state_dir: Path, *, kind: str, signature: str) -> None:
    """Additive-only telemetry: a Bash/Grep call that missed the exact-string
    cache, logged by coarse signature. Never read by any hook and never
    changes hook behavior — purely observational data for a later, real
    decision about widening cacheable_bash_command()/grep_key() — see
    BACKLOG.md's Token-Reduction Strategies. Fail-open, same as savings_log.append()."""
    if not signature:
        return
    path = state_dir / "near_misses.jsonl"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"kind": kind, "signature": signature, "ts": time.time()}) + "\n")
    except OSError:
        pass


def check_context_cache(
    payload: HookPayload,
    *,
    state_dir: Path,
    enabled: bool,
    grep_ttl: int,
    bash_ttl: int | None = None,
    event_name: str = "PreToolUse",
    log=None,
    session: tuple[str, str] | None = None,
) -> tuple[int, str, str]:
    if not enabled:
        return 0, "", ""
    if payload.tool_name not in {"Read", "Grep", "Bash"}:
        return 0, "", ""

    sid, ssrc = session or ("local-session", "local")

    state = get_state(
        state_dir,
        str(payload.transcript_path) if payload.transcript_path is not None else None,
    )
    state["call"] = state.get("call", 0) + 1
    inp = payload.tool_input or {}

    if payload.tool_name == "Bash":
        if event_name == "PostToolUse":
            record_bash(state, inp, len(payload.tool_output or ""))
            save_state(state_dir, state)
            return 0, "", ""
        msg, saved_chars = check_bash(state, inp, bash_ttl if bash_ttl is not None else grep_ttl)
        if msg:
            if log:
                log({
                    "strategy": STRATEGY_CONTEXT_CACHE_BASH,
                    "basis": "measured",
                    "kept_chars": 0,
                    "elided_chars": saved_chars,
                    "content_kind": "cached_bash",
                    "where": bash_command(inp),
                    "session_id": sid,
                    "session_source": ssrc,
                })
            save_state(state_dir, state)
            return 2, "", msg
        record_near_miss(state_dir, kind="bash", signature=near_miss_signature(bash_command(inp)))
    elif payload.tool_name == "Read":
        file_path = str(inp.get("file_path", ""))
        if not file_path:
            save_state(state_dir, state)
            return 0, "", ""
        offset = inp.get("offset") or None
        limit = inp.get("limit") or None
        if event_name == "PostToolUse":
            # Record only once the Read actually executed. Recording at
            # PreToolUse time is wrong: a sibling PreToolUse hook (e.g.
            # search-first) can still deny this same call, and PostToolUse
            # never fires for a denied call — so gating the record on
            # PostToolUse means a denied Read is never falsely marked served.
            record_read(state, file_path, offset, limit)
            save_state(state_dir, state)
            return 0, "", ""
        msg = check_read(state, file_path, offset, limit)
        if msg:
            if log:
                saved_chars = blocked_read_chars(file_path, offset, limit)
                log({
                    "strategy": STRATEGY_CONTEXT_CACHE_READ,
                    "basis": "measured",
                    "kept_chars": 0,
                    "elided_chars": saved_chars,
                    "content_kind": "cached_read",
                    "where": file_path,
                    "session_id": sid,
                    "session_source": ssrc,
                })
            save_state(state_dir, state)
            return 2, "", msg
    else:
        if event_name == "PostToolUse":
            record_grep(state, inp)
            save_state(state_dir, state)
            return 0, "", ""
        msg = check_grep(state, inp, grep_ttl)
        if msg:
            if log:
                log({
                    "strategy": STRATEGY_CONTEXT_CACHE_GREP,
                    "basis": "measured",
                    "kept_chars": 0,
                    "elided_chars": 0,
                    "content_kind": "cached_grep",
                    "where": inp.get("pattern", ""),
                    "session_id": sid,
                    "session_source": ssrc,
                })
            save_state(state_dir, state)
            return 2, "", msg
        record_near_miss(state_dir, kind="grep", signature=str(inp.get("pattern") or inp.get("query") or "")[:80])

    save_state(state_dir, state)
    return 0, "", ""
