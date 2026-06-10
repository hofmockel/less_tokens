"""Integration tests for --agent codex install mode."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(REPO))
from install import (
    _dir_is_writable,
    _install_specs,
    copy_tree,
    handle_agents_md,
    handle_search_config,
    wire_codex_hooks_json,
    unwire_codex_hooks_json,
)

FRAGMENT = REPO / "agents" / "codex" / "instructions" / "AGENTS.md.fragment"


# ---------------------------------------------------------------------------
# Directory structure
# ---------------------------------------------------------------------------

class TestCodexInstallDirStructure:
    def test_less_tokens_tools_created(self, tmp_path):
        copy_tree(
            REPO / ".claude" / "tools",
            tmp_path / ".less_tokens" / "tools",
            tmp_path,
            force=True, overwrite_modified=True, label=".less_tokens/tools/",
            exclude=frozenset({"search_config.py"}),
        )
        tools_dir = tmp_path / ".less_tokens" / "tools"
        assert tools_dir.is_dir()
        assert (tools_dir / "search.py").exists()
        assert (tools_dir / "embeddings.py").exists()

    def test_less_tokens_schema_created(self, tmp_path):
        copy_tree(
            REPO / ".claude" / "schema",
            tmp_path / ".less_tokens" / "schema",
            tmp_path,
            force=True, overwrite_modified=True, label=".less_tokens/schema/",
        )
        assert (tmp_path / ".less_tokens" / "schema").is_dir()

    def test_codex_specs_exclude_claude_hooks(self):
        specs = _install_specs(caveman=False, agents={"codex"})
        dest_dirs = [s[1] for s in specs]
        assert ".claude/hooks" not in dest_dirs

    def test_search_config_written_to_less_tokens(self, tmp_path):
        handle_search_config(
            REPO / ".claude" / "tools" / "search_config.py",
            tmp_path / ".less_tokens" / "tools" / "search_config.py",
            tmp_path,
            False, False,
        )
        config_text = (tmp_path / ".less_tokens" / "tools" / "search_config.py").read_text()
        assert "active_state_dir" in config_text

    def test_search_config_has_agent_aware_sentinel(self, tmp_path):
        handle_search_config(
            REPO / ".claude" / "tools" / "search_config.py",
            tmp_path / ".less_tokens" / "tools" / "search_config.py",
            tmp_path,
            False, False,
        )
        config_text = (tmp_path / ".less_tokens" / "tools" / "search_config.py").read_text()
        assert "_STATE_AGENT_AWARE" in config_text


# ---------------------------------------------------------------------------
# Writability probe
# ---------------------------------------------------------------------------

class TestCodexWritabilityProbe:
    @pytest.mark.skipif(sys.platform == "win32", reason="chmod has no effect on Windows")
    def test_non_writable_codex_dir_excluded_from_specs(self, tmp_path):
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir()
        codex_dir.chmod(0o555)
        try:
            specs = _install_specs(caveman=False, agents={"codex"}, target_root=tmp_path)
            dest_dirs = [s[1] for s in specs]
            assert not any(".codex/hooks" in d for d in dest_dirs)
            # skill goes somewhere — .agents/ or .less_tokens/ depending on writability
            assert any("skills" in d for d in dest_dirs)
        finally:
            codex_dir.chmod(0o755)

    def test_writable_codex_dir_included_in_specs(self, tmp_path):
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir()
        specs = _install_specs(caveman=False, agents={"codex"}, target_root=tmp_path)
        dest_dirs = [s[1] for s in specs]
        assert any(".codex/hooks" in d for d in dest_dirs)

    def test_dir_is_writable_helper_on_existing_dir(self, tmp_path):
        d = tmp_path / "sub"
        d.mkdir()
        assert _dir_is_writable(tmp_path, "sub")

    def test_dir_is_writable_helper_on_missing_dir(self, tmp_path):
        assert _dir_is_writable(tmp_path, "nonexistent")


# ---------------------------------------------------------------------------
# AGENTS.md creation
# ---------------------------------------------------------------------------

class TestCodexAgentsMd:
    def test_agents_md_created(self, tmp_path):
        handle_agents_md(FRAGMENT, tmp_path)
        assert (tmp_path / "AGENTS.md").exists()

    def test_agents_md_contains_token_discipline(self, tmp_path):
        handle_agents_md(FRAGMENT, tmp_path)
        content = (tmp_path / "AGENTS.md").read_text()
        assert "Token Discipline" in content

    def test_agents_md_contains_search_command(self, tmp_path):
        handle_agents_md(FRAGMENT, tmp_path)
        content = (tmp_path / "AGENTS.md").read_text()
        assert "search.py" in content


# ---------------------------------------------------------------------------
# wire_codex_hooks_json / unwire_codex_hooks_json
# ---------------------------------------------------------------------------

class TestWireCodexHooksJson:
    def test_creates_hooks_json_with_correct_structure(self, tmp_path):
        hooks_json = tmp_path / ".codex" / "hooks.json"
        entries = [("PostToolUse", "Edit|Write", "python index-refresh.py")]
        added, present = wire_codex_hooks_json(hooks_json, entries)
        assert added == 1
        assert present == 0
        data = json.loads(hooks_json.read_text())
        assert "hooks" in data
        assert data["hooks"][0]["event"] == "PostToolUse"

    def test_idempotent_second_wire(self, tmp_path):
        hooks_json = tmp_path / ".codex" / "hooks.json"
        entries = [("PostToolUse", "Edit|Write", "python index-refresh.py")]
        wire_codex_hooks_json(hooks_json, entries)
        added, present = wire_codex_hooks_json(hooks_json, entries)
        assert added == 0
        assert present == 1

    def test_dry_run_does_not_write_file(self, tmp_path):
        hooks_json = tmp_path / ".codex" / "hooks.json"
        wire_codex_hooks_json(hooks_json,
                              [("PostToolUse", "Edit", "python x.py")], dry_run=True)
        assert not hooks_json.exists()

    def test_unwire_removes_codex_hook_entries(self, tmp_path):
        hooks_json = tmp_path / ".codex" / "hooks.json"
        cmd = f"python {REPO}/agents/codex/hooks/index-refresh.py"
        wire_codex_hooks_json(hooks_json, [("PostToolUse", "Edit", cmd)])
        removed = unwire_codex_hooks_json(hooks_json, REPO, dry_run=False)
        assert removed == 1
        data = json.loads(hooks_json.read_text())
        assert data["hooks"] == []

    def test_unwire_leaves_non_less_tokens_entries(self, tmp_path):
        hooks_json = tmp_path / ".codex" / "hooks.json"
        hooks_json.parent.mkdir(parents=True)
        hooks_json.write_text(json.dumps({
            "hooks": [{"event": "PostToolUse", "command": "python user_hook.py"}]
        }))
        unwire_codex_hooks_json(hooks_json, REPO, dry_run=False)
        data = json.loads(hooks_json.read_text())
        assert len(data["hooks"]) == 1
