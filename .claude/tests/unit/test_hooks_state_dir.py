"""State-dir isolation: Claude and Codex hooks write/read separate state directories."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).parent.parent.parent.parent
CLAUDE_HOOKS = REPO / ".claude" / "hooks"
CODEX_HOOKS = REPO / "agents" / "codex" / "hooks"

_BASE_ENV = {
    **os.environ,
    "PYTHONPATH": str(REPO / ".claude" / "tools"),
    "LESS_TOKENS_REPO": str(REPO),
}


def run_hook(
    hook_path: Path, payload: dict, extra_env: dict | None = None
) -> tuple[int, str, str]:
    env = {**_BASE_ENV, **(extra_env or {})}
    result = subprocess.run(
        [sys.executable, str(hook_path)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
    )
    return result.returncode, result.stdout, result.stderr


# ---------------------------------------------------------------------------
# compact-trigger state dir isolation
# ---------------------------------------------------------------------------


class TestCompactTriggerStateDirIsolation:
    def test_codex_hook_writes_state_to_custom_dir(self, tmp_path):
        """Codex compact-trigger writes its state file to LESS_TOKENS_STATE_DIR."""
        transcript = tmp_path / "session.json"
        transcript.write_text("x" * 800_000)
        state_dir = tmp_path / "codex_state"

        code, stdout, stderr = run_hook(
            CODEX_HOOKS / "compact-trigger.py",
            {
                "hook_event_name": "PreCompact",
                "trigger": "auto",
                "transcript_path": str(transcript),
            },
            extra_env={
                "LESS_TOKENS_STATE_DIR": str(state_dir),
                "LESS_TOKENS_AGENT": "codex",
            },
        )
        assert (code, stdout, stderr) == (0, "", "")
        assert (state_dir / "compact-peak").exists()

    def test_claude_hook_writes_state_to_custom_dir(self, tmp_path):
        """Claude compact-trigger also respects LESS_TOKENS_STATE_DIR."""
        transcript = tmp_path / "session.json"
        transcript.write_text("x" * 800_000)
        state_dir = tmp_path / "claude_state"

        code, _, _ = run_hook(
            CLAUDE_HOOKS / "compact-trigger.py",
            {
                "tool_name": "Bash",
                "tool_input": {},
                "tool_result": "",
                "transcript_path": str(transcript),
            },
            extra_env={"LESS_TOKENS_STATE_DIR": str(state_dir)},
        )
        assert code == 2
        assert (state_dir / "compact-trigger-last").exists()

    def test_codex_and_claude_state_files_are_independent(self, tmp_path):
        """Firing compact-trigger for Codex does not write to Claude state dir."""
        transcript = tmp_path / "session.json"
        transcript.write_text("x" * 800_000)
        codex_state = tmp_path / "codex_state"
        claude_state = tmp_path / "claude_state"
        claude_state.mkdir()

        run_hook(
            CODEX_HOOKS / "compact-trigger.py",
            {
                "tool_name": "Bash",
                "tool_input": {},
                "tool_response": "",
                "transcript_path": str(transcript),
            },
            extra_env={"LESS_TOKENS_STATE_DIR": str(codex_state)},
        )
        assert not (claude_state / "compact-trigger-last").exists()


# ---------------------------------------------------------------------------
# search-first state dir isolation
# ---------------------------------------------------------------------------


class TestSearchFirstStateDirIsolation:
    def test_gate_clears_when_sentinel_in_state_dir(self, tmp_path):
        """search-first (Claude) passes when last-search exists in LESS_TOKENS_STATE_DIR."""
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        (state_dir / "last-search").touch()

        code, _, _ = run_hook(
            CLAUDE_HOOKS / "search-first.py",
            {
                "tool_name": "Read",
                "tool_input": {"file_path": str(REPO / "README.md")},
                "tool_result": "",
            },
            extra_env={"LESS_TOKENS_STATE_DIR": str(state_dir)},
        )
        assert code == 0

    def test_gate_blocks_when_sentinel_in_different_dir(self, tmp_path):
        """A sentinel in the wrong state dir does not satisfy the Claude gate."""
        wrong_dir = tmp_path / "wrong"
        wrong_dir.mkdir()
        (wrong_dir / "last-search").touch()
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        code, _, _ = run_hook(
            CLAUDE_HOOKS / "search-first.py",
            {
                "tool_name": "Read",
                "tool_input": {"file_path": str(REPO / "README.md")},
                "tool_result": "",
            },
            extra_env={"LESS_TOKENS_STATE_DIR": str(empty_dir)},
        )
        assert code == 2

    def test_codex_search_first_unknown_tool_passes(self, tmp_path):
        """Codex search-first exits 0 for unknown tool names (best-effort, not a sandbox)."""
        state_dir = tmp_path / "state"
        state_dir.mkdir()

        code, _, _ = run_hook(
            CODEX_HOOKS / "search-first.py",
            {"tool_name": "SomeFutureTool", "tool_input": {}, "tool_response": ""},
            extra_env={"LESS_TOKENS_STATE_DIR": str(state_dir)},
        )
        assert code == 0


# ---------------------------------------------------------------------------
# v2 budget-plane state dir isolation (events.jsonl contamination regression)
# ---------------------------------------------------------------------------


class TestBudgetObserverStateDirIsolation:
    """Pins the bug where events_path() derived .less_tokens/state from the
    repo root regardless of LESS_TOKENS_STATE_DIR, writing real telemetry
    events into the production repo's events.jsonl during every test run."""

    REAL_EVENTS_LOG = REPO / ".less_tokens" / "state" / "events.jsonl"

    def _real_log_line_count(self) -> int:
        if not self.REAL_EVENTS_LOG.exists():
            return 0
        return len(self.REAL_EVENTS_LOG.read_text(encoding="utf-8").splitlines())

    def test_claude_budget_observer_writes_events_to_custom_dir(self, tmp_path):
        """budget-observer.py must write v2 events under LESS_TOKENS_STATE_DIR, never repo state."""
        state_dir = tmp_path / "state"
        before = self._real_log_line_count()

        run_hook(
            CLAUDE_HOOKS / "budget-observer.py",
            {
                "tool_name": "Bash",
                "tool_input": {"command": "pwd"},
                "tool_result": "some output",
            },
            extra_env={"LESS_TOKENS_STATE_DIR": str(state_dir)},
        )

        after = self._real_log_line_count()
        assert after == before, (
            "budget-observer.py wrote to the production events.jsonl instead of "
            "LESS_TOKENS_STATE_DIR — state-dir override was ignored"
        )
        custom_events = state_dir / ".less_tokens" / "state" / "events.jsonl"
        assert custom_events.exists(), (
            "expected v2 event to land under the overridden state dir"
        )

    def test_codex_budget_observer_writes_events_to_custom_dir(self, tmp_path):
        """Codex's budget-observer.py shares budget_hook_outcome — same fix, same coverage."""
        state_dir = tmp_path / "state"
        before = self._real_log_line_count()

        run_hook(
            CODEX_HOOKS / "budget-observer.py",
            {
                "tool_name": "Bash",
                "tool_input": {"command": "pwd"},
                "tool_response": "some output",
            },
            extra_env={
                "LESS_TOKENS_STATE_DIR": str(state_dir),
                "LESS_TOKENS_AGENT": "codex",
            },
        )

        after = self._real_log_line_count()
        assert after == before, (
            "Codex budget-observer.py wrote to the production events.jsonl instead of "
            "LESS_TOKENS_STATE_DIR — state-dir override was ignored"
        )
        custom_events = state_dir / ".less_tokens" / "state" / "events.jsonl"
        assert custom_events.exists(), (
            "expected v2 event to land under the overridden state dir"
        )
