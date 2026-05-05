#!/usr/bin/env python3
"""Append one JSON record to savings.jsonl when TRACK_SAVINGS is enabled.

Imported by hooks and tools; no-ops silently when tracking is off.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "tools"))

try:
    from search_config import STATE_DIR, TRACK_SAVINGS
except Exception:
    TRACK_SAVINGS = False
    STATE_DIR = BASE / ".claude" / "state"

_LOG_FILE = STATE_DIR / "savings.jsonl"


def append(record: dict) -> None:
    """Append record to savings.jsonl. No-op when TRACK_SAVINGS is False."""
    if not TRACK_SAVINGS:
        return
    record.setdefault("ts", time.time())
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        with _LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception:
        pass
