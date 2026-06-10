"""Unit tests for _install_specs() and selected_agents() with different agent sets."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(REPO))
from install import _install_specs, selected_agents


class TestSelectedAgents:
    def test_claude_returns_claude_set(self):
        assert selected_agents("claude") == {"claude"}

    def test_codex_returns_codex_set(self):
        assert selected_agents("codex") == {"codex"}

    def test_both_returns_both(self):
        assert selected_agents("both") == {"claude", "codex"}


class TestInstallSpecsAgentSelector:
    def test_claude_only_includes_hooks(self):
        specs = _install_specs(caveman=False, agents={"claude"})
        dest_dirs = [s[1] for s in specs]
        assert ".claude/hooks" in dest_dirs

    def test_claude_only_no_less_tokens_entries(self):
        specs = _install_specs(caveman=False, agents={"claude"})
        dest_dirs = [s[1] for s in specs]
        assert not any(".less_tokens" in d for d in dest_dirs)

    def test_codex_only_no_claude_hooks(self):
        specs = _install_specs(caveman=False, agents={"codex"})
        dest_dirs = [s[1] for s in specs]
        assert ".claude/hooks" not in dest_dirs

    def test_codex_only_includes_less_tokens_tools(self):
        specs = _install_specs(caveman=False, agents={"codex"})
        dest_dirs = [s[1] for s in specs]
        assert any(".less_tokens/tools" in d for d in dest_dirs)

    def test_codex_only_includes_less_tokens_schema(self):
        specs = _install_specs(caveman=False, agents={"codex"})
        dest_dirs = [s[1] for s in specs]
        assert any(".less_tokens/schema" in d for d in dest_dirs)

    def test_both_includes_claude_hooks(self):
        specs = _install_specs(caveman=False, agents={"claude", "codex"})
        dest_dirs = [s[1] for s in specs]
        assert ".claude/hooks" in dest_dirs

    def test_both_includes_less_tokens(self):
        specs = _install_specs(caveman=False, agents={"claude", "codex"})
        dest_dirs = [s[1] for s in specs]
        assert any(".less_tokens" in d for d in dest_dirs)

    def test_caveman_adds_rules_for_claude(self):
        on_dirs = [s[1] for s in _install_specs(caveman=True, agents={"claude"})]
        off_dirs = [s[1] for s in _install_specs(caveman=False, agents={"claude"})]
        assert ".claude/rules" in on_dirs
        assert ".claude/rules" not in off_dirs

    def test_caveman_not_added_for_codex_only(self):
        specs = _install_specs(caveman=True, agents={"codex"})
        dest_dirs = [s[1] for s in specs]
        assert ".claude/rules" not in dest_dirs

    def test_default_agents_matches_explicit_claude(self):
        assert _install_specs(caveman=False) == _install_specs(caveman=False, agents={"claude"})
