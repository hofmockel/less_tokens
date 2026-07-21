#!/usr/bin/env python3
"""Add bounded, task-focused context when a Codex subagent starts."""
from __future__ import annotations

import json
import sys

from _codex_runtime import bootstrap, load_json_stdin

bootstrap()

GUIDANCE = (
    "Keep the delegated scope narrow. Return only: files changed, findings, "
    "verification, and unresolved risks. Do not paste source bodies, diffs, logs, "
    "or prior search output; cite paths and line numbers instead."
)


def main() -> int:
    payload = load_json_stdin()
    if not payload or payload.get("hook_event_name") != "SubagentStart":
        return 0
    if not isinstance(payload.get("agent_id"), str):
        return 0
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SubagentStart",
            "additionalContext": GUIDANCE,
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
