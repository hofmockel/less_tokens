"""Tests for build_claude_hook_entries in install.py."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from install import build_claude_hook_entries


def _args(**kwargs) -> argparse.Namespace:
    defaults = {"truncate": False, "compact": False, "caveman": False}
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def _cmds(tmp_path, **kwargs):
    venv_py = tmp_path / ".venv" / "bin" / "python"
    entries = build_claude_hook_entries(venv_py, tmp_path, _args(**kwargs))
    return [(ev, matcher, cmd) for ev, matcher, cmd in entries]


class TestBuildClaudeHookEntries:
    def test_core_hook_set_does_not_regress(self, tmp_path):
        entries = _cmds(tmp_path)
        commands = [cmd for _, _, cmd in entries]
        assert len(entries) == 15
        for name in [
            "budget-observer.py",
            "search-first.py",
            "read-guard.py",
            "auto-slice.py",
            "grep-first-read.py",
            "read-after-edit.py",
            "context-cache.py",
            "post-edit-diff.py",
            "index-refresh.py",
            "claudemd-budget.py",
            "lean-output.py",
            "listing-guard.py",
            "savings-html.py",
        ]:
            assert any(name in cmd for cmd in commands), f"{name} missing from Claude hooks"

    def test_optional_hook_set_does_not_regress(self, tmp_path):
        entries = _cmds(tmp_path, truncate=True, compact=True, caveman=True)
        commands = [cmd for _, _, cmd in entries]
        assert len(entries) == 18
        assert any("truncate-output.py" in cmd for cmd in commands)
        assert any("compact-trigger.py" in cmd for cmd in commands)
        assert any("caveman-reminder.py" in cmd for cmd in commands)

    def test_claudemd_budget_wired_as_post_tool_use(self, tmp_path):
        entries = _cmds(tmp_path)
        hooks = [(ev, m) for ev, m, cmd in entries if "claudemd-budget.py" in cmd]
        assert hooks, "claudemd-budget.py not in hook entries"
        assert hooks[0] == ("PostToolUse", "Edit|Write")

    def test_budget_observer_sees_post_search_outputs(self, tmp_path):
        entries = _cmds(tmp_path)
        hooks = [(ev, m) for ev, m, cmd in entries if "budget-observer.py" in cmd]
        assert ("PostToolUse", "Read|Grep|Glob|Bash|Edit|Write") in hooks

    def test_index_refresh_wired(self, tmp_path):
        entries = _cmds(tmp_path)
        assert any("index-refresh.py" in cmd for _, _, cmd in entries)

    def test_search_first_wired_for_read_and_grep(self, tmp_path):
        entries = _cmds(tmp_path)
        sf = [(ev, m) for ev, m, cmd in entries if "search-first.py" in cmd]
        matchers = {m for _, m in sf}
        assert "Read" in matchers
        assert "Grep" in matchers

    def test_caveman_reminder_only_with_caveman_flag(self, tmp_path):
        without = _cmds(tmp_path, caveman=False)
        with_ = _cmds(tmp_path, caveman=True)
        assert not any("caveman-reminder.py" in cmd for _, _, cmd in without)
        assert any("caveman-reminder.py" in cmd for _, _, cmd in with_)

    def test_compact_trigger_only_with_compact_flag(self, tmp_path):
        without = _cmds(tmp_path, compact=False)
        with_ = _cmds(tmp_path, compact=True)
        assert not any("compact-trigger.py" in cmd for _, _, cmd in without)
        assert any("compact-trigger.py" in cmd for _, _, cmd in with_)

    def test_truncate_hook_only_with_truncate_flag(self, tmp_path):
        without = _cmds(tmp_path, truncate=False)
        with_ = _cmds(tmp_path, truncate=True)
        assert not any("truncate-output.py" in cmd for _, _, cmd in without)
        assert any("truncate-output.py" in cmd for _, _, cmd in with_)
