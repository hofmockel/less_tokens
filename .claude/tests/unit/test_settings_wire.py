"""Unit tests for wire_settings in install.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from install import wire_settings


class TestWireSettings:
    def test_creates_file_and_returns_added(self, tmp_path):
        settings = tmp_path / ".claude" / "settings.local.json"
        added, present = wire_settings(
            settings, [("PreToolUse", "Read", "python hook.py")]
        )
        assert added == 1
        assert present == 0
        assert settings.exists()

    def test_correct_json_structure(self, tmp_path):
        settings = tmp_path / "settings.local.json"
        wire_settings(settings, [("PreToolUse", "Read", "python hook.py")])
        data = json.loads(settings.read_text())
        assert "hooks" in data
        hook_list = data["hooks"]["PreToolUse"]
        assert len(hook_list) == 1
        assert hook_list[0]["matcher"] == "Read"
        assert hook_list[0]["hooks"][0]["command"] == "python hook.py"
        assert hook_list[0]["hooks"][0]["type"] == "command"

    def test_idempotent_second_call(self, tmp_path):
        settings = tmp_path / "settings.local.json"
        entries = [("PreToolUse", "Read", "python hook.py")]
        wire_settings(settings, entries)
        added, present = wire_settings(settings, entries)
        assert added == 0
        assert present == 1

    def test_no_duplicate_entries(self, tmp_path):
        settings = tmp_path / "settings.local.json"
        entries = [("PreToolUse", "Read", "python hook.py")]
        for _ in range(3):
            wire_settings(settings, entries)
        data = json.loads(settings.read_text())
        assert len(data["hooks"]["PreToolUse"]) == 1

    def test_multiple_event_types(self, tmp_path):
        settings = tmp_path / "settings.local.json"
        entries = [
            ("PreToolUse", "Read", "python search-first.py"),
            ("PostToolUse", "Edit|Write", "python index-refresh.py"),
        ]
        added, present = wire_settings(settings, entries)
        assert added == 2
        data = json.loads(settings.read_text())
        assert "PreToolUse" in data["hooks"]
        assert "PostToolUse" in data["hooks"]

    def test_merges_with_existing_settings(self, tmp_path):
        settings = tmp_path / "settings.local.json"
        settings.write_text(json.dumps({"some_other_key": True}))
        wire_settings(settings, [("PreToolUse", "Read", "python hook.py")])
        data = json.loads(settings.read_text())
        assert data["some_other_key"] is True
        assert "hooks" in data

    def test_handles_malformed_existing_json(self, tmp_path):
        settings = tmp_path / "settings.local.json"
        settings.write_text("not-json{{{")
        added, _ = wire_settings(settings, [("PreToolUse", "Read", "python hook.py")])
        assert added == 1

    def test_different_commands_same_matcher_both_added(self, tmp_path):
        settings = tmp_path / "settings.local.json"
        wire_settings(settings, [("PostToolUse", ".*", "python hook_a.py")])
        added, _ = wire_settings(settings, [("PostToolUse", ".*", "python hook_b.py")])
        assert added == 1
        data = json.loads(settings.read_text())
        matchers = [e["matcher"] for e in data["hooks"]["PostToolUse"]]
        assert matchers.count(".*") == 2
