"""Shared subagent fan-out telemetry logic (SA2).

Pairs a spawned subagent's prompt size (captured at ``PreToolUse:Task``) with
its return size (captured at ``PostToolUse:Task``) into one event per spawn,
so SA3/SA4/SA5's benefit claims can be measured instead of guessed.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path


def state_file(state_dir: Path) -> Path:
    return state_dir / "subagent-fanout-pending.json"


def load_state(state_dir: Path) -> dict:
    try:
        return json.loads(state_file(state_dir).read_text())
    except Exception:
        return {"pending": []}


def save_state(state_dir: Path, state: dict) -> None:
    try:
        path = state_file(state_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state))
    except Exception as exc:
        print(f"warning: failed to save subagent fanout state to {state_file(state_dir)}: {exc}", file=sys.stderr)


def spawn_key(tool_input: dict) -> str:
    """Stable content key for a Task spawn, used to pair Pre with Post.

    Concurrent spawns with identical ``tool_input`` collide on this key;
    :func:`pop_spawn` matches FIFO, so same-content concurrent spawns still
    pair in spawn order rather than crossing entries or dropping a pairing.
    """
    payload = json.dumps(tool_input, sort_keys=True, default=str)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def subagent_type_of(tool_input: dict) -> str:
    value = tool_input.get("subagent_type")
    return value if isinstance(value, str) and value.strip() else "unknown"


def record_spawn(state: dict, *, key: str, subagent_type: str, prompt_chars: int,
                  ts: float) -> None:
    state.setdefault("pending", []).append({
        "key": key,
        "subagent_type": subagent_type,
        "prompt_chars": prompt_chars,
        "ts": ts,
    })


def pop_spawn(state: dict, key: str) -> dict | None:
    """Pop the oldest pending entry matching ``key`` (FIFO), or ``None``."""
    pending = state.setdefault("pending", [])
    for i, entry in enumerate(pending):
        if entry.get("key") == key:
            return pending.pop(i)
    return None


def build_fanout_record(*, subagent_type: str, prompt_chars: int, return_chars: int,
                         session_id: str, session_source: str) -> dict:
    return {
        "event": "subagent_fanout",
        "subagent_type": subagent_type,
        "prompt_chars": prompt_chars,
        "return_chars": return_chars,
        "session_id": session_id,
        "session_source": session_source,
    }


def handle_pre_spawn(state_dir: Path, tool_input: dict, *, now: float | None = None) -> None:
    state = load_state(state_dir)
    record_spawn(
        state,
        key=spawn_key(tool_input),
        subagent_type=subagent_type_of(tool_input),
        prompt_chars=len(json.dumps(tool_input, default=str)),
        ts=now if now is not None else time.time(),
    )
    save_state(state_dir, state)


def handle_post_return(state_dir: Path, tool_input: dict, return_chars: int, *,
                        session_id: str, session_source: str) -> dict:
    """Pop the matching spawn (if any) and build one combined fan-out record.

    An unmatched Post (no observed Pre — e.g. the hook was installed
    mid-session) still emits a record with ``prompt_chars=0`` rather than
    dropping the event: Post firing is the true "one event per spawn" signal.
    """
    state = load_state(state_dir)
    entry = pop_spawn(state, spawn_key(tool_input))
    save_state(state_dir, state)
    prompt_chars = entry["prompt_chars"] if entry else 0
    subagent_type = entry["subagent_type"] if entry else subagent_type_of(tool_input)
    return build_fanout_record(
        subagent_type=subagent_type,
        prompt_chars=prompt_chars,
        return_chars=return_chars,
        session_id=session_id,
        session_source=session_source,
    )
