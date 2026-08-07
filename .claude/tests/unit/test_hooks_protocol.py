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


REPO = Path(__file__).parent.parent.parent.parent
HOOKS = REPO / ".claude" / "hooks"

_ENV = {**os.environ, "PYTHONPATH": str(REPO / ".claude" / "tools")}


def run_hook(
    hook_name: str, payload: dict, extra_env: dict | None = None
) -> tuple[int, str, str]:
    result = subprocess.run(
        [sys.executable, str(HOOKS / hook_name)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env={**_ENV, **(extra_env or {})},
    )
    return result.returncode, result.stdout, result.stderr


# ---------------------------------------------------------------------------
# truncate-output.py
# ---------------------------------------------------------------------------


class TestTruncateOutput:
    def test_passes_when_under_limit(self):
        code, _, _ = run_hook(
            "truncate-output.py",
            {
                "tool_name": "Bash",
                "tool_result": "x" * 100,
            },
        )
        assert code == 0

    def test_blocks_when_over_limit(self):
        # PostToolUse exit code 2 only shows stderr (tool already ran) — it
        # never replaces the delivered output. Actually reducing what Claude
        # sees requires hookSpecificOutput.updatedToolOutput on exit 0 (see
        # code.claude.com/docs/en/hooks.md#posttooluse-decision-control).
        code, stdout, _ = run_hook(
            "truncate-output.py",
            {
                "tool_name": "Bash",
                "tool_result": "x" * 10_000,
            },
        )
        assert code == 0
        out = json.loads(stdout)["hookSpecificOutput"]
        assert "omitted" in out["additionalContext"]

    def test_bash_keeps_head_and_tail(self):
        # Each line ~110 chars; 200 lines = ~22 000 chars, well above the 4 000 ceiling
        lines = [f"line {i:04d}: " + "x" * 100 for i in range(200)]
        code, stdout, _ = run_hook(
            "truncate-output.py",
            {
                "tool_name": "Bash",
                "tool_result": "\n".join(lines),
            },
        )
        assert code == 0
        out = json.loads(stdout)["hookSpecificOutput"]
        assert "line 0000" in out["updatedToolOutput"]
        assert "line 0199" in out["updatedToolOutput"]
        assert "omitted" in out["additionalContext"]

    def test_read_uses_char_split(self):
        large = "A" * 3000 + "B" * 3000
        code, stdout, _ = run_hook(
            "truncate-output.py",
            {
                "tool_name": "Read",
                "tool_result": large,
            },
        )
        assert code == 0
        out = json.loads(stdout)["hookSpecificOutput"]
        assert "omitted" in out["additionalContext"]

    def test_ignored_for_unknown_tool(self):
        code, _, _ = run_hook(
            "truncate-output.py",
            {
                "tool_name": "WebSearch",
                "tool_result": "x" * 10_000,
            },
        )
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
    """Every case redirects LESS_TOKENS_STATE_DIR to tmp_path — compact-trigger.py
    also appends a session_size sample to near_misses.jsonl on every invocation
    (BACKLOG.md's compaction-threshold instrumentation), and this suite used to
    run unisolated, seeding the real repo's telemetry with round-number fixture
    sizes (600_000 etc.) that don't reflect real session sizes."""

    def test_passes_when_under_limit(self, tmp_path):
        transcript = tmp_path / "t.jsonl"
        transcript.write_text("x" * 1000)
        state_dir = tmp_path / "state"
        code, _, _ = run_hook(
            "compact-trigger.py",
            {
                "tool_name": "Bash",
                "transcript_path": str(transcript),
            },
            extra_env={"LESS_TOKENS_STATE_DIR": str(state_dir)},
        )
        assert code == 0

    def test_fires_when_over_limit(self, tmp_path):
        transcript = tmp_path / "t.jsonl"
        transcript.write_text("x" * 800_000)
        state_dir = tmp_path / "state"
        code, _, stderr = run_hook(
            "compact-trigger.py",
            {
                "tool_name": "Bash",
                "transcript_path": str(transcript),
            },
            extra_env={"LESS_TOKENS_STATE_DIR": str(state_dir)},
        )
        assert code == 2
        assert "compact" in stderr.lower()

    def test_no_transcript_path_passes(self, tmp_path):
        state_dir = tmp_path / "state"
        code, _, _ = run_hook(
            "compact-trigger.py",
            {"tool_name": "Bash"},
            extra_env={"LESS_TOKENS_STATE_DIR": str(state_dir)},
        )
        assert code == 0

    def test_nonexistent_transcript_passes(self, tmp_path):
        state_dir = tmp_path / "state"
        code, _, _ = run_hook(
            "compact-trigger.py",
            {
                "tool_name": "Bash",
                "transcript_path": str(tmp_path / "nonexistent.jsonl"),
            },
            extra_env={"LESS_TOKENS_STATE_DIR": str(state_dir)},
        )
        assert code == 0

    def test_malformed_json_exits_zero(self, tmp_path):
        state_dir = tmp_path / "state"
        result = subprocess.run(
            [sys.executable, str(HOOKS / "compact-trigger.py")],
            input="{{bad",
            capture_output=True,
            text=True,
            env={**_ENV, "LESS_TOKENS_STATE_DIR": str(state_dir)},
        )
        assert result.returncode == 0

    def test_hysteresis_suppresses_repeat_fire(self, tmp_path):
        transcript = tmp_path / "t.jsonl"
        transcript.write_text("x" * 800_000)
        state_dir = tmp_path / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / "compact-trigger-last").write_text("800000")
        code, _, _ = run_hook(
            "compact-trigger.py",
            {
                "tool_name": "Bash",
                "transcript_path": str(transcript),
            },
            extra_env={"LESS_TOKENS_STATE_DIR": str(state_dir)},
        )
        # Within hysteresis window — should not re-fire
        assert code == 0


# ---------------------------------------------------------------------------
# search-first.py
# ---------------------------------------------------------------------------


class TestSearchFirst:
    def test_non_read_tool_passes(self):
        code, _, _ = run_hook(
            "search-first.py",
            {
                "tool_name": "Bash",
                "tool_input": {"command": "ls"},
            },
        )
        assert code == 0

    def test_outside_repo_file_passes(self):
        code, _, _ = run_hook(
            "search-first.py",
            {
                "tool_name": "Read",
                "tool_input": {"file_path": "/tmp/unrelated.py"},
            },
        )
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
        code, _, _ = run_hook(
            "search-first.py",
            {
                "tool_name": "Read",
                "tool_input": {},
            },
        )
        assert code == 0


# ---------------------------------------------------------------------------
# index-refresh.py
# ---------------------------------------------------------------------------


class TestIndexRefresh:
    def test_non_edit_write_tool_passes(self):
        code, _, _ = run_hook(
            "index-refresh.py",
            {
                "tool_name": "Bash",
                "tool_input": {"command": "ls"},
            },
        )
        assert code == 0

    def test_outside_repo_file_passes(self):
        code, _, _ = run_hook(
            "index-refresh.py",
            {
                "tool_name": "Edit",
                "tool_input": {"file_path": "/tmp/unrelated.py"},
            },
        )
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
        code, _, _ = run_hook(
            "index-refresh.py",
            {
                "tool_name": "Edit",
                "tool_input": {},
            },
        )
        assert code == 0
