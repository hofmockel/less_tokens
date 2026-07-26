"""SA1: PostToolUse:Task hook caps an oversized subagent return before it
lands in the parent's transcript, preserving pass/fail/blocker-style fields."""
from __future__ import annotations

import io
import json
import sys

from tests.conftest import REPO_ROOT, load_hook

from agents.common.hooks.payload import HookPayload
from agents.common.hooks.truncate_output import check_truncate_subagent, truncate_subagent

HOOK = REPO_ROOT / ".claude" / "hooks" / "subagent-cap.py"


def _payload(tool_name: str, tool_output: str) -> HookPayload:
    return HookPayload(
        agent="claude",
        tool_name=tool_name,
        tool_input={},
        tool_output=tool_output,
        transcript_path=None,
        touched_files=(),
    )


class TestTruncateSubagent:
    def test_short_text_untouched(self):
        assert truncate_subagent("short", 100) == "short"

    def test_key_fields_kept_verbatim_when_digest_fits(self):
        body = "Verdict: CONFIRMED\nsome irrelevant filler line\n" + ("noise " * 200)
        result = truncate_subagent(body, 50)
        assert "Verdict: CONFIRMED" in result
        assert "chars of subagent output omitted" in result
        assert "irrelevant filler line" not in result

    def test_falls_back_to_head_tail_when_no_key_fields(self):
        body = "x" * 5000
        result = truncate_subagent(body, 200)
        assert len(result) <= 260
        assert result.startswith("x")
        assert "chars omitted" in result

    def test_disabled_when_ceiling_zero(self):
        body = "x" * 5000
        assert truncate_subagent(body, 0) == body


class TestCheckTruncateSubagent:
    def test_ignores_non_task_tools(self):
        payload = _payload("Bash", "x" * 5000)
        code, stdout, stderr = check_truncate_subagent(payload, max_chars=100)
        assert (code, stdout, stderr) == (0, "", "")

    def test_caps_oversized_task_return(self):
        payload = _payload("Task", "Recommendation: ship it\n" + ("y" * 5000))
        code, stdout, stderr = check_truncate_subagent(payload, max_chars=100)
        assert code == 2
        assert "Recommendation: ship it" in stdout
        assert "chars omitted" in stderr

    def test_under_ceiling_is_noop(self):
        payload = _payload("Task", "small return")
        code, stdout, stderr = check_truncate_subagent(payload, max_chars=1000)
        assert (code, stdout, stderr) == (0, "", "")


class TestSubagentCapHook:
    def test_oversized_return_emits_updated_tool_output(self, monkeypatch):
        mod = load_hook(HOOK)
        monkeypatch.setattr(mod, "MAX_SUBAGENT_OUTPUT_CHARS", 100)
        monkeypatch.setattr(mod, "_log_savings", lambda _r: None)

        big = "Verdict: PASS\n" + ("z" * 5000)
        payload = json.dumps({"tool_name": "Task", "tool_result": big})
        monkeypatch.setattr(sys, "stdin", io.StringIO(payload))

        captured = io.StringIO()
        monkeypatch.setattr(sys, "stdout", captured)

        rc = mod.main()

        assert rc == 0, "PostToolUse must exit 0 for updatedToolOutput to take effect"
        out = json.loads(captured.getvalue())
        updated = out["hookSpecificOutput"]["updatedToolOutput"]
        assert out["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
        assert len(updated) < len(big)
        assert "Verdict: PASS" in updated
        assert "chars omitted" in out["hookSpecificOutput"]["additionalContext"]

    def test_short_return_leaves_output_untouched(self, monkeypatch):
        mod = load_hook(HOOK)
        monkeypatch.setattr(mod, "MAX_SUBAGENT_OUTPUT_CHARS", 10_000)
        monkeypatch.setattr(mod, "_log_savings", lambda _r: None)

        payload = json.dumps({"tool_name": "Task", "tool_result": "short"})
        monkeypatch.setattr(sys, "stdin", io.StringIO(payload))

        captured = io.StringIO()
        monkeypatch.setattr(sys, "stdout", captured)

        rc = mod.main()

        assert rc == 0
        assert captured.getvalue() == ""

    def test_non_task_tool_ignored(self, monkeypatch):
        mod = load_hook(HOOK)
        monkeypatch.setattr(mod, "MAX_SUBAGENT_OUTPUT_CHARS", 10)
        monkeypatch.setattr(mod, "_log_savings", lambda _r: None)

        payload = json.dumps({"tool_name": "Bash", "tool_result": "x" * 500})
        monkeypatch.setattr(sys, "stdin", io.StringIO(payload))

        captured = io.StringIO()
        monkeypatch.setattr(sys, "stdout", captured)

        rc = mod.main()

        assert rc == 0
        assert captured.getvalue() == ""


class TestSubagentCapWiring:
    def test_hook_wired_as_posttooluse_task_in_settings_json(self):
        """PT6: without this, subagent-cap.py can silently fall out of
        .claude/settings.json (as it did for PT1) with every unit test above
        still green, since they load the hook module directly rather than
        going through the live wiring."""
        settings = json.loads((REPO_ROOT / ".claude" / "settings.json").read_text())
        matches = [
            h
            for block in settings["hooks"].get("PostToolUse", [])
            if block.get("matcher") == "Task"
            for h in block.get("hooks", [])
            if "subagent-cap.py" in h.get("command", "")
        ]
        assert matches, (
            "subagent-cap.py must be wired as a PostToolUse:Task hook in .claude/settings.json"
        )
