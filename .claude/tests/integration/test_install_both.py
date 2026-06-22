"""Integration tests for --agent both mode and per-agent selective uninstall."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(REPO))
from install import (
    _install_specs,
    _our_hook_names,
    unwire_codex_hooks_json,
    unwire_settings,
    wire_codex_hooks_json,
    wire_settings,
)


# ---------------------------------------------------------------------------
# Both-mode specs
# ---------------------------------------------------------------------------

class TestBothModeSpecs:
    def test_includes_claude_hooks(self):
        specs = _install_specs(caveman=False, agents={"claude", "codex"})
        dest_dirs = [s[1] for s in specs]
        assert ".claude/hooks" in dest_dirs

    def test_includes_shared_less_tokens_tools(self):
        specs = _install_specs(caveman=False, agents={"claude", "codex"})
        dest_dirs = [s[1] for s in specs]
        assert ".less_tokens/tools" in dest_dirs

    def test_includes_less_tokens_schema(self):
        specs = _install_specs(caveman=False, agents={"claude", "codex"})
        dest_dirs = [s[1] for s in specs]
        assert any(".less_tokens/schema" in d for d in dest_dirs)

    def test_no_codex_index_db_path(self):
        """index.db always lives under .claude/, never .codex/."""
        specs = _install_specs(caveman=False, agents={"claude", "codex"})
        dest_dirs = [s[1] for s in specs]
        assert not any(".codex/index.db" in d for d in dest_dirs)


# ---------------------------------------------------------------------------
# _our_hook_names
# ---------------------------------------------------------------------------

class TestOurHookNames:
    def test_claude_only_returns_claude_hook_filenames(self):
        names = _our_hook_names(REPO, agents={"claude"})
        assert any("index-refresh" in n for n in names)
        assert any("search-first" in n for n in names)
        assert any("compact-trigger" in n for n in names)

    def test_codex_only_returns_codex_hook_filenames(self):
        names = _our_hook_names(REPO, agents={"codex"})
        assert any("index-refresh" in n for n in names)
        assert any("compact-trigger" in n for n in names)

    def test_both_is_superset_of_each_agent(self):
        claude = _our_hook_names(REPO, agents={"claude"})
        codex = _our_hook_names(REPO, agents={"codex"})
        both = _our_hook_names(REPO, agents={"claude", "codex"})
        assert both >= claude
        assert both >= codex


# ---------------------------------------------------------------------------
# Selective uninstall
# ---------------------------------------------------------------------------

class TestSelectiveUnwire:
    def test_unwire_claude_settings_does_not_touch_codex_hooks_json(self, tmp_path):
        hooks_json = tmp_path / ".codex" / "hooks.json"
        codex_entries = [("PostToolUse", "Edit",
                          f"python {REPO}/agents/codex/hooks/index-refresh.py")]
        wire_codex_hooks_json(hooks_json, codex_entries)
        original = hooks_json.read_text()

        settings = tmp_path / ".claude" / "settings.json"
        unwire_settings(settings, REPO, dry_run=False)
        assert hooks_json.read_text() == original

    def test_unwire_codex_hooks_json_does_not_touch_claude_settings(self, tmp_path):
        settings = tmp_path / ".claude" / "settings.json"
        entries = [
            ("PreToolUse", "Read",
             f"python {REPO}/.claude/hooks/search-first.py"),
        ]
        wire_settings(settings, entries)
        original = settings.read_text()

        hooks_json = tmp_path / ".codex" / "hooks.json"
        unwire_codex_hooks_json(hooks_json, REPO, dry_run=False)
        assert settings.read_text() == original

    def test_uninstall_claude_preserves_codex_hooks(self, tmp_path):
        hooks_json = tmp_path / ".codex" / "hooks.json"
        wire_codex_hooks_json(hooks_json,
                              [("PostToolUse", "Edit", "python user_hook.py")])
        assert hooks_json.exists()

        settings = tmp_path / ".claude" / "settings.json"
        unwire_settings(settings, REPO, dry_run=False)
        assert hooks_json.exists()


# ---------------------------------------------------------------------------
# Idempotency in both mode
# ---------------------------------------------------------------------------

class TestIdempotentBothMode:
    def test_double_wire_settings_no_duplicates(self, tmp_path):
        settings = tmp_path / ".claude" / "settings.json"
        entries = [("PreToolUse", "Read", "python search-first.py")]
        wire_settings(settings, entries)
        wire_settings(settings, entries)

        data = json.loads(settings.read_text())
        pre = data["hooks"].get("PreToolUse", [])
        commands = [h["command"] for e in pre for h in e.get("hooks", [])]
        assert commands.count("python search-first.py") == 1

    def test_double_wire_codex_no_duplicates(self, tmp_path):
        hooks_json = tmp_path / ".codex" / "hooks.json"
        entries = [("PostToolUse", "Edit", "python index-refresh.py")]
        wire_codex_hooks_json(hooks_json, entries)
        wire_codex_hooks_json(hooks_json, entries)

        data = json.loads(hooks_json.read_text())
        commands = [h["command"] for h in data["hooks"]]
        assert commands.count("python index-refresh.py") == 1

    def test_multiple_entries_all_wired_once(self, tmp_path):
        hooks_json = tmp_path / ".codex" / "hooks.json"
        entries = [
            ("PostToolUse", "Edit|Write", "python index-refresh.py"),
            ("PreToolUse",  "mcp__.*",    "python search-first.py"),
        ]
        wire_codex_hooks_json(hooks_json, entries)
        added2, present2 = wire_codex_hooks_json(hooks_json, entries)
        assert added2 == 0
        assert present2 == 2
