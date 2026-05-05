"""Hook protocol tests — verify stdin/stdout/exit-code contract for each hook.

Hooks are run as subprocesses (matching real Claude Code behaviour).
search-first.py and index-refresh.py load search_config at import time, so
PYTHONPATH is set to include tools/ to satisfy the import without a venv.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent.parent
HOOKS = REPO / "hooks"

_ENV = {**os.environ, "PYTHONPATH": str(REPO / "tools")}

# compact-trigger.py computes REPO as __file__.parent.parent.parent — three levels
# up from its own location.  When run from the source tree that resolves to the
# *parent* of the repo, not the repo root.  The hook writes its state file there.
_HOOK_REPO = (HOOKS / "compact-trigger.py").resolve().parent.parent.parent
_COMPACT_STATE = _HOOK_REPO / ".claude" / "state" / "compact-trigger-last"


def _clear_compact_state() -> None:
    """Remove the compact-trigger state file so hysteresis cannot suppress a fire."""
    _COMPACT_STATE.unlink(missing_ok=True)


def run_hook(hook_name: str, payload: dict) -> tuple[int, str, str]:
    result = subprocess.run(
        [sys.executable, str(HOOKS / hook_name)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=_ENV,
    )
    return result.returncode, result.stdout, result.stderr


# ---------------------------------------------------------------------------
# truncate-output.py
# ---------------------------------------------------------------------------

class TestTruncateOutput:
    def test_passes_when_under_limit(self):
        code, _, _ = run_hook("truncate-output.py", {
            "tool_name": "Bash",
            "tool_result": "x" * 100,
        })
        assert code == 0

    def test_blocks_when_over_limit(self):
        code, stdout, stderr = run_hook("truncate-output.py", {
            "tool_name": "Bash",
            "tool_result": "x" * 10_000,
        })
        assert code == 2
        assert "omitted" in stdout

    def test_bash_keeps_head_and_tail(self):
        # Each line ~110 chars; 200 lines = ~22 000 chars, well above the 4 000 ceiling
        lines = [f"line {i:04d}: " + "x" * 100 for i in range(200)]
        code, stdout, _ = run_hook("truncate-output.py", {
            "tool_name": "Bash",
            "tool_result": "\n".join(lines),
        })
        assert code == 2
        assert "line 0000" in stdout
        assert "line 0199" in stdout
        assert "omitted" in stdout

    def test_read_uses_char_split(self):
        large = "A" * 3000 + "B" * 3000
        code, stdout, _ = run_hook("truncate-output.py", {
            "tool_name": "Read",
            "tool_result": large,
        })
        assert code == 2
        assert "omitted" in stdout

    def test_ignored_for_unknown_tool(self):
        code, _, _ = run_hook("truncate-output.py", {
            "tool_name": "WebSearch",
            "tool_result": "x" * 10_000,
        })
        assert code == 0

    def test_malformed_json_exits_zero(self):
        result = subprocess.run(
            [sys.executable, str(HOOKS / "truncate-output.py")],
            input="not-json!!!",
            capture_output=True,
            text=True,
            env=_ENV,
        )
        assert result.returncode == 0

    def test_empty_payload_exits_zero(self):
        code, _, _ = run_hook("truncate-output.py", {})
        assert code == 0


# ---------------------------------------------------------------------------
# compact-trigger.py
# ---------------------------------------------------------------------------

class TestCompactTrigger:
    def test_passes_when_under_limit(self, tmp_path):
        transcript = tmp_path / "t.jsonl"
        transcript.write_text("x" * 1000)
        code, _, _ = run_hook("compact-trigger.py", {
            "tool_name": "Bash",
            "transcript_path": str(transcript),
        })
        assert code == 0

    def test_fires_when_over_limit(self, tmp_path):
        _clear_compact_state()
        transcript = tmp_path / "t.jsonl"
        transcript.write_text("x" * 600_000)
        code, _, stderr = run_hook("compact-trigger.py", {
            "tool_name": "Bash",
            "transcript_path": str(transcript),
        })
        _clear_compact_state()
        assert code == 2
        assert "compact" in stderr.lower()

    def test_no_transcript_path_passes(self):
        code, _, _ = run_hook("compact-trigger.py", {"tool_name": "Bash"})
        assert code == 0

    def test_nonexistent_transcript_passes(self, tmp_path):
        code, _, _ = run_hook("compact-trigger.py", {
            "tool_name": "Bash",
            "transcript_path": str(tmp_path / "nonexistent.jsonl"),
        })
        assert code == 0

    def test_malformed_json_exits_zero(self):
        result = subprocess.run(
            [sys.executable, str(HOOKS / "compact-trigger.py")],
            input="{{bad",
            capture_output=True,
            text=True,
            env=_ENV,
        )
        assert result.returncode == 0

    def test_hysteresis_suppresses_repeat_fire(self, tmp_path):
        transcript = tmp_path / "t.jsonl"
        transcript.write_text("x" * 600_000)
        # Write state at the path the hook actually reads (HOOK_REPO, not REPO)
        _COMPACT_STATE.parent.mkdir(parents=True, exist_ok=True)
        _COMPACT_STATE.write_text("600000")
        code, _, _ = run_hook("compact-trigger.py", {
            "tool_name": "Bash",
            "transcript_path": str(transcript),
        })
        _clear_compact_state()
        # Within hysteresis window — should not re-fire
        assert code == 0


# ---------------------------------------------------------------------------
# search-first.py
# ---------------------------------------------------------------------------

class TestSearchFirst:
    def test_non_read_tool_passes(self):
        code, _, _ = run_hook("search-first.py", {
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
        })
        assert code == 0

    def test_outside_repo_file_passes(self):
        code, _, _ = run_hook("search-first.py", {
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/unrelated.py"},
        })
        assert code == 0

    def test_malformed_json_exits_zero(self):
        result = subprocess.run(
            [sys.executable, str(HOOKS / "search-first.py")],
            input="not-json",
            capture_output=True,
            text=True,
            env=_ENV,
        )
        assert result.returncode == 0

    def test_missing_file_path_passes(self):
        code, _, _ = run_hook("search-first.py", {
            "tool_name": "Read",
            "tool_input": {},
        })
        assert code == 0


# ---------------------------------------------------------------------------
# index-refresh.py
# ---------------------------------------------------------------------------

class TestIndexRefresh:
    def test_non_edit_write_tool_passes(self):
        code, _, _ = run_hook("index-refresh.py", {
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
        })
        assert code == 0

    def test_outside_repo_file_passes(self):
        code, _, _ = run_hook("index-refresh.py", {
            "tool_name": "Edit",
            "tool_input": {"file_path": "/tmp/unrelated.py"},
        })
        assert code == 0

    def test_malformed_json_exits_zero(self):
        result = subprocess.run(
            [sys.executable, str(HOOKS / "index-refresh.py")],
            input="not-json",
            capture_output=True,
            text=True,
            env=_ENV,
        )
        assert result.returncode == 0

    def test_missing_file_path_passes(self):
        code, _, _ = run_hook("index-refresh.py", {
            "tool_name": "Edit",
            "tool_input": {},
        })
        assert code == 0
