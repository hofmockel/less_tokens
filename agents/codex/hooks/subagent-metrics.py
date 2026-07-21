#!/usr/bin/env python3
"""Record bounded Codex subagent prompt, final, and parent-visible sizes."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from _codex_runtime import bootstrap, load_json_stdin

REPO = bootstrap()


def _char_count(value: object) -> int:
    if value is None:
        return 0
    if isinstance(value, str):
        return len(value)
    return len(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str))


def _prompt_chars(payload: dict) -> int:
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0
    for field in ("message", "prompt"):
        value = tool_input.get(field)
        if isinstance(value, str):
            return len(value)
    return _char_count(tool_input)


def _state_path() -> Path:
    configured = os.environ.get("LESS_TOKENS_STATE_DIR")
    state_dir = Path(configured) if configured else REPO / ".less_tokens" / "state"
    return state_dir / "subagent-metrics.jsonl"


def _record(payload: dict) -> dict | None:
    event = payload.get("hook_event_name")
    if event in {"PreToolUse", "PostToolUse"} and payload.get("tool_name") != "Agent":
        return None
    phases = {
        "PreToolUse": "prompt",
        "PostToolUse": "parent_absorbed",
        "SubagentStart": "child_start",
        "SubagentStop": "child_final",
    }
    phase = phases.get(event)
    if phase is None:
        return None
    return {
        "version": 1,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "event": "codex_subagent_measurement",
        "phase": phase,
        "session_id": payload.get("session_id", ""),
        "turn_id": payload.get("turn_id", ""),
        "tool_use_id": payload.get("tool_use_id", ""),
        "agent_id": payload.get("agent_id", ""),
        "agent_type": payload.get("agent_type", ""),
        "prompt_chars": _prompt_chars(payload) if phase == "prompt" else 0,
        "child_final_chars": _char_count(payload.get("last_assistant_message"))
        if phase == "child_final" else 0,
        "parent_absorbed_chars": _char_count(payload.get("tool_response"))
        if phase == "parent_absorbed" else 0,
    }


def main() -> int:
    payload = load_json_stdin()
    if not payload:
        return 0
    record = _record(payload)
    if record is None:
        return 0
    try:
        path = _state_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
