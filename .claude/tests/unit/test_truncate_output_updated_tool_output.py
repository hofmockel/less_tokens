"""Regression: truncate-output.py must actually replace what Claude sees.

BACKLOG.md "truncate-output hook reports truncation inconsistent with
delivered content": the hook computed a truncated string, printed it to
stdout, and exited 2 — but PostToolUse exit code 2 only shows stderr to
Claude (the tool already ran); stdout is never substituted for the original
tool output (verified against code.claude.com/docs/en/hooks.md). The fix is
to emit hookSpecificOutput.updatedToolOutput on a normal exit 0 return, which
is the documented mechanism for a PostToolUse hook to replace tool output.
"""

from __future__ import annotations

import io
import json
import sys

from tests.conftest import REPO_ROOT, load_hook

HOOK = REPO_ROOT / ".claude" / "hooks" / "truncate-output.py"


def test_truncation_emits_updated_tool_output_and_exits_zero(monkeypatch):
    mod = load_hook(HOOK)
    monkeypatch.setattr(mod, "MAX_TOOL_OUTPUT_CHARS", 100)
    monkeypatch.setattr(mod, "_log_savings", lambda _r: None)

    big = "x" * 10_000
    payload = json.dumps({"tool_name": "WebFetch", "tool_result": big})
    monkeypatch.setattr(sys, "stdin", io.StringIO(payload))

    captured = io.StringIO()
    monkeypatch.setattr(sys, "stdout", captured)

    rc = mod.main()

    assert rc == 0, "PostToolUse must exit 0 for updatedToolOutput to take effect"
    out = json.loads(captured.getvalue())
    updated = out["hookSpecificOutput"]["updatedToolOutput"]
    assert out["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
    assert len(updated) < len(big), (
        "updatedToolOutput must be the truncated text, not the original"
    )
    assert "chars omitted" in out["hookSpecificOutput"]["additionalContext"]


def test_no_truncation_leaves_output_untouched(monkeypatch):
    mod = load_hook(HOOK)
    monkeypatch.setattr(mod, "MAX_TOOL_OUTPUT_CHARS", 10_000)
    monkeypatch.setattr(mod, "_log_savings", lambda _r: None)

    payload = json.dumps({"tool_name": "WebFetch", "tool_result": "short"})
    monkeypatch.setattr(sys, "stdin", io.StringIO(payload))

    captured = io.StringIO()
    monkeypatch.setattr(sys, "stdout", captured)

    rc = mod.main()

    assert rc == 0
    assert captured.getvalue() == ""
