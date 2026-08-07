"""Bug 17: truncate-output.py logged 'truncation' savings even when disabled.

When MAX_TOOL_OUTPUT_CHARS == 0, the hook should pass through immediately
without calling _log_savings at all, even for very large results.
"""

from __future__ import annotations

import sys
from tests.conftest import REPO_ROOT, load_hook

sys.path.insert(0, str(REPO_ROOT / ".claude" / "tools"))


def test_no_savings_logged_when_disabled(monkeypatch, tmp_path):
    """With MAX_TOOL_OUTPUT_CHARS=0, _log_savings must never be called."""
    mod = load_hook(REPO_ROOT / ".claude" / "hooks" / "truncate-output.py")
    monkeypatch.setattr(mod, "MAX_TOOL_OUTPUT_CHARS", 0)

    logged: list[dict] = []
    monkeypatch.setattr(mod, "_log_savings", logged.append)

    # Simulate a large Bash result that would trigger truncation if enabled.
    import json
    import io

    payload = json.dumps({"tool_name": "Bash", "tool_result": "x" * 10_000})
    monkeypatch.setattr(sys, "stdin", io.StringIO(payload))

    rc = mod.main()

    assert rc == 0, "hook must exit 0 (pass-through) when disabled"
    assert logged == [], (
        "truncate-output.py called _log_savings even though MAX_TOOL_OUTPUT_CHARS=0 (Bug 17)"
    )
