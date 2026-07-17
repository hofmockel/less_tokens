"""Tests for build_claude_hook_entries in install.py."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from install import build_claude_hook_entries


def _args(**kwargs) -> argparse.Namespace:
    defaults = {
        "truncate": False, "compact": False, "caveman": False,
        "no_truncate": False, "no_compact": False, "no_caveman": False,
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def _cmds(tmp_path, **kwargs):
    venv_py = tmp_path / ".venv" / "bin" / "python"
    entries = build_claude_hook_entries(venv_py, tmp_path, _args(**kwargs))
    return [(ev, matcher, cmd) for ev, matcher, cmd in entries]


class TestBuildClaudeHookEntries:
    def test_core_hook_set_does_not_regress(self, tmp_path):
        # CL2: Claude installs wire the optional savings hooks by default, so a
        # flagless install now yields the full 18-hook set. G15: terse-output
        # and savings-html each gained a SubagentStop wire alongside Stop, so
        # the count is 20. context-cache gained a PostToolUse Read|Grep wire
        # (BACKLOG.md: denied Reads were falsely recorded as served), so 21.
        # continue-freshness added (PreToolUse Read, Claude-only), so 22.
        # SA1: subagent-cap added (PostToolUse Task, Claude-only), so 23.
        entries = _cmds(tmp_path)
        commands = [cmd for _, _, cmd in entries]
        assert len(entries) == 23
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
            "continue-freshness.py",
        ]:
            assert any(name in cmd for cmd in commands), f"{name} missing from Claude hooks"

    def test_optional_hooks_on_by_default(self, tmp_path):
        # CL2: no flags needed — Claude gets truncate/compact/caveman by default.
        entries = _cmds(tmp_path)
        commands = [cmd for _, _, cmd in entries]
        assert any("truncate-output.py" in cmd for cmd in commands)
        assert any("subagent-cap.py" in cmd for cmd in commands)
        assert any("compact-trigger.py" in cmd for cmd in commands)
        assert any("caveman-reminder.py" in cmd for cmd in commands)

    def test_explicit_flags_are_back_compat_no_op(self, tmp_path):
        # Passing the old opt-in flags still works and matches the default set.
        default = _cmds(tmp_path)
        explicit = _cmds(tmp_path, truncate=True, compact=True, caveman=True)
        assert default == explicit
        assert len(explicit) == 23

    def test_subagent_stop_wired_for_terse_and_savings(self, tmp_path):
        # G15: a Claude child's final turn fires SubagentStop, not Stop.
        entries = _cmds(tmp_path)
        for name in ("caveman-reminder.py", "savings-html.py"):
            events = {ev for ev, _, cmd in entries if name in cmd}
            assert events == {"Stop", "SubagentStop"}, f"{name}: {events}"

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

    def test_caveman_reminder_opt_out_with_no_caveman(self, tmp_path):
        default = _cmds(tmp_path)
        opted_out = _cmds(tmp_path, no_caveman=True)
        assert any("caveman-reminder.py" in cmd for _, _, cmd in default)
        assert not any("caveman-reminder.py" in cmd for _, _, cmd in opted_out)

    def test_compact_trigger_opt_out_with_no_compact(self, tmp_path):
        default = _cmds(tmp_path)
        opted_out = _cmds(tmp_path, no_compact=True)
        assert any("compact-trigger.py" in cmd for _, _, cmd in default)
        assert not any("compact-trigger.py" in cmd for _, _, cmd in opted_out)

    def test_truncate_hook_opt_out_with_no_truncate(self, tmp_path):
        default = _cmds(tmp_path)
        opted_out = _cmds(tmp_path, no_truncate=True)
        assert any("truncate-output.py" in cmd for _, _, cmd in default)
        assert not any("truncate-output.py" in cmd for _, _, cmd in opted_out)

    def test_subagent_cap_wired_for_task_and_opts_out_with_no_truncate(self, tmp_path):
        # SA1: rides the "truncate" optional flag — same size-capping family.
        default = _cmds(tmp_path)
        hooks = [(ev, m) for ev, m, cmd in default if "subagent-cap.py" in cmd]
        assert hooks == [("PostToolUse", "Task")]
        opted_out = _cmds(tmp_path, no_truncate=True)
        assert not any("subagent-cap.py" in cmd for _, _, cmd in opted_out)
