"""Shared .less_tokens runtime state helpers."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


def state_dir(root: Path) -> Path:
    return root / ".less_tokens" / "state"


def session_state_path(root: Path, agent: str) -> Path:
    return state_dir(root) / f"{agent}-session.json"


def shared_project_state_path(root: Path) -> Path:
    return state_dir(root) / "shared-project-state.json"


def load_json(path: Path) -> dict[str, Any]:
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except (OSError, json.JSONDecodeError):
        return {}
    return {}


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def touch_session(root: Path, agent: str, *, session_id: str, run_id: str) -> None:
    data = load_json(session_state_path(root, agent))
    data.update({
        "agent": agent,
        "session_id": session_id,
        "run_id": run_id,
        "updated_at": time.time(),
    })
    save_json(session_state_path(root, agent), data)


def advice_state_path(root: Path) -> Path:
    return state_dir(root) / "advice-rate-limit.json"


def should_emit_advice(root: Path, key: str, *, window_seconds: int = 300) -> bool:
    """Return True when an advise-mode message should be shown.

    State failures fail open: noisy advice is worse than no state, but a broken
    state file must never suppress a useful replacement hint.
    """
    now = time.time()
    try:
        state = load_json(advice_state_path(root))
        last = float(state.get(key, 0) or 0)
        if last and now - last < window_seconds:
            return False
        state[key] = now
        save_json(advice_state_path(root), state)
    except (OSError, TypeError, ValueError):
        return True
    return True
