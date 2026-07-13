#!/usr/bin/env python3
"""Codex hook: record v2 budget telemetry without changing tool outcomes."""
from __future__ import annotations

import sys

from _codex_runtime import bootstrap, load_json_stdin, map_read

REPO = bootstrap()

from budget_observer import budget_hook_outcome  # noqa: E402

try:
    from agents.common.budget.advice import claude_hook_output  # noqa: E402
except Exception:
    from budget.advice import claude_hook_output  # type: ignore[no-redef]  # noqa: E402


def main() -> int:
    raw = load_json_stdin(map_read)
    if not raw:
        return 0
    outcome = budget_hook_outcome(raw, repo=REPO, agent="codex")
    if not outcome:
        return 0
    if outcome.message:
        if outcome.stream == "stderr":
            print(outcome.message, file=sys.stderr)
        else:
            print(claude_hook_output(outcome.message))
    return outcome.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
