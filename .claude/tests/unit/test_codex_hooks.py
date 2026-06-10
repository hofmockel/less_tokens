"""Codex adapter hook subprocess tests — stdin/stdout/exit-code contract."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent.parent.parent
CODEX_HOOKS = REPO / "agents" / "codex" / "hooks"

_ENV = {
    **os.environ,
    "PYTHONPATH": str(REPO / ".claude" / "tools"),
    "LESS_TOKENS_REPO": str(REPO),
}


def run_hook_with_env(hook_name: str, payload: dict, extra_env: dict | None = None) -> tuple[int, str, str]:
    env = {**_ENV, **(extra_env or {})}
    result = subprocess.run(
        [sys.executable, str(CODEX_HOOKS / hook_name)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
    )
    return result.returncode, result.stdout, result.stderr


# ---------------------------------------------------------------------------
# index-refresh.py
# ---------------------------------------------------------------------------

class TestCodexIndexRefresh:
    def test_apply_patch_exits_zero(self):
        """apply_patch always exits 0 — no VENV_PY check skips early."""
        code, _, _ = run_hook_with_env("index-refresh.py", {
            "tool_name": "apply_patch",
            "tool_input": {},
            "tool_response": "",
        })
        assert code == 0

    def test_unrelated_tool_exits_zero(self):
        code, _, _ = run_hook_with_env("index-refresh.py", {
            "tool_name": "Bash",
            "tool_input": {},
            "tool_response": "some output",
        })
        assert code == 0

    def test_edit_with_non_indexed_file_exits_zero(self, tmp_path):
        non_indexed = tmp_path / "binary.exe"
        non_indexed.touch()
        code, _, _ = run_hook_with_env("index-refresh.py", {
            "tool_name": "Edit",
            "tool_input": {"file_path": str(non_indexed)},
            "tool_response": "",
        })
        assert code == 0


# ---------------------------------------------------------------------------
# truncate-output.py
# ---------------------------------------------------------------------------

class TestCodexTruncateOutput:
    def test_passes_small_output(self):
        code, _, _ = run_hook_with_env("truncate-output.py", {
            "tool_name": "Bash",
            "tool_response": "small output",
        })
        assert code == 0

    def test_truncates_large_tool_response(self):
        code, stdout, stderr = run_hook_with_env("truncate-output.py", {
            "tool_name": "Bash",
            "tool_response": "x" * 10_000,
        })
        assert code == 2
        assert "omitted" in stdout or "omitted" in stderr

    def test_passes_non_targeted_tool(self):
        code, _, _ = run_hook_with_env("truncate-output.py", {
            "tool_name": "Edit",
            "tool_response": "x" * 10_000,
        })
        assert code == 0

    def test_truncates_large_filesystem_read(self):
        code, stdout, _ = run_hook_with_env("truncate-output.py", {
            "tool_name": "mcp__filesystem__read_file",
            "tool_response": "x" * 10_000,
        })
        assert code == 2
        assert "omitted" in stdout


# ---------------------------------------------------------------------------
# compact-trigger.py
# ---------------------------------------------------------------------------

class TestCodexCompactTrigger:
    def test_fires_with_large_transcript(self, tmp_path):
        transcript = tmp_path / "session.json"
        transcript.write_text("x" * 600_000)
        state_dir = tmp_path / "state"

        code, _, stderr = run_hook_with_env("compact-trigger.py", {
            "tool_name": "Bash",
            "tool_input": {},
            "tool_response": "",
            "transcript_path": str(transcript),
        }, extra_env={"LESS_TOKENS_STATE_DIR": str(state_dir)})

        assert code == 2
        assert "/compact" not in stderr
        assert "Codex" in stderr or "session" in stderr.lower()

    def test_passes_without_transcript(self):
        code, _, _ = run_hook_with_env("compact-trigger.py", {
            "tool_name": "Bash",
            "tool_input": {},
            "tool_response": "",
        })
        assert code == 0

    def test_message_does_not_contain_slash_compact(self, tmp_path):
        transcript = tmp_path / "session.json"
        transcript.write_text("x" * 600_000)
        state_dir = tmp_path / "state"

        _, _, stderr = run_hook_with_env("compact-trigger.py", {
            "tool_name": "Bash",
            "tool_input": {},
            "tool_response": "",
            "transcript_path": str(transcript),
        }, extra_env={"LESS_TOKENS_STATE_DIR": str(state_dir)})

        assert "/compact" not in stderr


# ---------------------------------------------------------------------------
# search-first.py
# ---------------------------------------------------------------------------

class TestCodexSearchFirst:
    def test_unknown_tool_exits_zero(self, tmp_path):
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        code, _, _ = run_hook_with_env("search-first.py", {
            "tool_name": "UnknownFutureTool",
            "tool_input": {},
            "tool_response": "",
        }, extra_env={"LESS_TOKENS_STATE_DIR": str(state_dir)})
        assert code == 0

    def test_filesystem_read_of_indexed_file_is_checked(self, tmp_path):
        """mcp__filesystem__read_file on an indexed file with no recent search is blocked."""
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        code, _, _ = run_hook_with_env("search-first.py", {
            "tool_name": "mcp__filesystem__read_file",
            "tool_input": {"path": str(REPO / "README.md")},
            "tool_response": "",
        }, extra_env={"LESS_TOKENS_STATE_DIR": str(state_dir)})
        assert code == 2

    def test_gate_clears_after_recent_search(self, tmp_path):
        """Gate passes when last-search sentinel is present in the state dir."""
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        (state_dir / "last-search").touch()
        code, _, _ = run_hook_with_env("search-first.py", {
            "tool_name": "mcp__filesystem__read_file",
            "tool_input": {"path": str(REPO / "README.md")},
            "tool_response": "",
        }, extra_env={"LESS_TOKENS_STATE_DIR": str(state_dir)})
        assert code == 0
