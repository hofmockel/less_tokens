#!/usr/bin/env python3
"""Codex PreCompact/PostCompact hook: snapshot state and measure compaction."""
from __future__ import annotations

import sys

from _codex_runtime import bootstrap, load_json_stdin

REPO = bootstrap()

from payload import normalize_codex  # noqa: E402
from agents.common.budget.compaction import refresh_compaction_snapshot  # noqa: E402
from agents.common.budget.config import load_budget_config  # noqa: E402
from compact_trigger import measure_compaction  # noqa: E402

try:
    from savings_log import append as _log_savings  # noqa: E402
    from savings_log import resolve_session  # noqa: E402
except Exception:
    def _log_savings(_r: dict) -> None:
        pass

    def resolve_session(_raw: dict | None) -> tuple[str, str]:
        return "local-session", "local"

try:
    from search_config import MAX_SESSION_CHARS, active_state_dir  # noqa: E402
    state_dir = active_state_dir()
except Exception:
    MAX_SESSION_CHARS = 750_000
    state_dir = REPO / ".less_tokens" / "state"

def main() -> int:
    raw = load_json_stdin()
    if not raw:
        return 0
    event = raw.get("hook_event_name")
    if event not in {"PreCompact", "PostCompact"}:
        return 0
    payload = normalize_codex(raw)
    if event == "PreCompact":
        try:
            refresh_compaction_snapshot(
                REPO,
                "codex",
                load_budget_config(REPO, agent="codex"),
            )
        except Exception:
            pass
    try:
        measure_compaction(
            payload,
            state_dir=state_dir,
            max_session_chars=MAX_SESSION_CHARS,
            log=_log_savings,
            session=resolve_session(raw),
        )
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
