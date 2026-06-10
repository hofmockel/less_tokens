"""Tests for agent-aware state directory selection in search_config."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(REPO / ".claude" / "tools"))


class TestStateDirectoryConstants:
    def test_state_dir_equals_claude_state_dir(self):
        from search_config import STATE_DIR, CLAUDE_STATE_DIR
        assert STATE_DIR == CLAUDE_STATE_DIR

    def test_sentinel_present(self):
        from search_config import _STATE_AGENT_AWARE
        assert _STATE_AGENT_AWARE is True

    def test_codex_state_dir_under_less_tokens(self):
        from search_config import CODEX_STATE_DIR, BASE
        assert CODEX_STATE_DIR == BASE / ".less_tokens" / "state"

    def test_claude_state_dir_under_claude(self):
        from search_config import CLAUDE_STATE_DIR, CLAUDE_DIR
        assert CLAUDE_STATE_DIR == CLAUDE_DIR / "state"


class TestStateDirFor:
    def test_claude_returns_claude_dir(self):
        from search_config import state_dir_for, CLAUDE_STATE_DIR
        assert state_dir_for("claude") == CLAUDE_STATE_DIR

    def test_codex_returns_codex_dir(self):
        from search_config import state_dir_for, CODEX_STATE_DIR
        assert state_dir_for("codex") == CODEX_STATE_DIR

    def test_none_returns_state_dir(self):
        from search_config import state_dir_for, STATE_DIR
        assert state_dir_for(None) == STATE_DIR

    def test_unknown_agent_returns_state_dir(self):
        from search_config import state_dir_for, STATE_DIR
        assert state_dir_for("unknown_agent") == STATE_DIR


class TestActiveStateDir:
    def test_explicit_env_wins_over_agent_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LESS_TOKENS_STATE_DIR", str(tmp_path))
        monkeypatch.setenv("LESS_TOKENS_AGENT", "codex")
        from search_config import active_state_dir
        assert active_state_dir() == tmp_path

    def test_agent_claude_env(self, monkeypatch):
        monkeypatch.delenv("LESS_TOKENS_STATE_DIR", raising=False)
        monkeypatch.setenv("LESS_TOKENS_AGENT", "claude")
        from search_config import active_state_dir, CLAUDE_STATE_DIR
        assert active_state_dir() == CLAUDE_STATE_DIR

    def test_agent_codex_env(self, monkeypatch):
        monkeypatch.delenv("LESS_TOKENS_STATE_DIR", raising=False)
        monkeypatch.setenv("LESS_TOKENS_AGENT", "codex")
        from search_config import active_state_dir, CODEX_STATE_DIR
        assert active_state_dir() == CODEX_STATE_DIR

    def test_no_env_returns_default_state_dir(self, monkeypatch):
        monkeypatch.delenv("LESS_TOKENS_STATE_DIR", raising=False)
        monkeypatch.delenv("LESS_TOKENS_AGENT", raising=False)
        from search_config import active_state_dir, STATE_DIR
        assert active_state_dir() == STATE_DIR

    def test_explicit_env_returns_path_object(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LESS_TOKENS_STATE_DIR", str(tmp_path))
        monkeypatch.delenv("LESS_TOKENS_AGENT", raising=False)
        from search_config import active_state_dir
        result = active_state_dir()
        assert isinstance(result, Path)
        assert result == tmp_path
