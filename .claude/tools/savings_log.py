#!/usr/bin/env python3
"""Append one JSON record to savings.jsonl. Always on; local-only.

Imported by hooks and tools. Tracking is unconditional from the first session
of every install — there is no enable flag. The log is written locally to
`state/savings.jsonl` and never transmitted.

Escape hatch: set ``LESS_TOKENS_NO_STATS=1`` to disable local logging. It lives
outside ``search_config.py`` on purpose, so the default mental model stays
"local telemetry is on".

Records store **exact characters** (the free, deterministic truth) under the
schema documented in ``stats_plan.md``: ``basis``/``kept_chars``/``elided_chars``
/``content_kind``/``where``/``session_id``/``session_source`` plus an optional
``correlation_id``. Tokens are never stored — they are derived at report time.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent.parent
CLAUDE_DIR = BASE / ".claude"
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from search_config import active_state_dir
    STATE_DIR = active_state_dir()
except Exception:
    STATE_DIR = CLAUDE_DIR / "state"

_LOG_FILE = STATE_DIR / "savings.jsonl"

# Canonical strategy registry — the single source of truth for every ``strategy``
# value an emitter is allowed to write. ``stats.py`` derives its label map and
# measured/upper-bound partition from this dict instead of hand-maintaining a
# second list, so emit (here) and consume (stats.py) cannot drift apart again.
# basis: "measured" — bytes actually removed before reaching the model (exact).
#        "upper_bound" — counterfactual/avoided cost, not an exact removal.
STRATEGY_TRUNCATION = "truncation"
STRATEGY_COMPACTION = "compaction"
STRATEGY_CONTEXT_CACHE_READ = "context-cache-read"
STRATEGY_CONTEXT_CACHE_GREP = "context-cache-grep"
STRATEGY_CONTEXT_CACHE_BASH = "context-cache-bash"
STRATEGY_SEARCH_BLOCKED = "search-blocked"
STRATEGY_SEARCH = "search"

_KNOWN_STRATEGIES: dict[str, tuple[str, str]] = {
    STRATEGY_TRUNCATION:           ("Truncation", "measured"),
    STRATEGY_COMPACTION:           ("Compaction", "measured"),
    STRATEGY_CONTEXT_CACHE_READ:   ("Cached read (repeat)", "measured"),
    STRATEGY_CONTEXT_CACHE_GREP:   ("Cached grep (repeat)", "measured"),
    STRATEGY_CONTEXT_CACHE_BASH:   ("Cached bash (repeat)", "measured"),
    STRATEGY_SEARCH_BLOCKED:       ("Search-first block", "upper_bound"),
    STRATEGY_SEARCH:               ("Search (vs full file)", "upper_bound"),
}


def _stats_disabled() -> bool:
    """True when the user opted out via LESS_TOKENS_NO_STATS."""
    return os.environ.get("LESS_TOKENS_NO_STATS", "").strip() not in ("", "0", "false", "False")


def resolve_session(raw: dict | None) -> tuple[str, str]:
    """Resolve a stable session id and its source, in priority order.

    1. Native payload field ``session_id``.
    2. Stable hash of ``transcript_path``.
    3. Environment ``LESS_TOKENS_SESSION_ID``.
    4. Last-resort local bucket ``local-session``.

    Returns ``(session_id, session_source)`` where source is one of
    ``payload`` | ``transcript_path`` | ``env`` | ``local``.
    """
    raw = raw or {}
    sid = raw.get("session_id")
    if isinstance(sid, str) and sid.strip():
        return sid.strip(), "payload"
    tp = raw.get("transcript_path")
    if isinstance(tp, str) and tp.strip():
        digest = hashlib.sha1(tp.strip().encode("utf-8")).hexdigest()[:12]
        return digest, "transcript_path"
    env_sid = os.environ.get("LESS_TOKENS_SESSION_ID", "").strip()
    if env_sid:
        return env_sid, "env"
    return "local-session", "local"


def append(record: dict) -> None:
    """Append record to savings.jsonl. No-op when LESS_TOKENS_NO_STATS is set.

    Stays failure-safe: any logging error is swallowed so a hook can never break.
    """
    if _stats_disabled():
        return
    record.setdefault("ts", time.time())
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        with _LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception:
        pass
