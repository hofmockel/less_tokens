"""Integration tests for --agent codex install mode."""
from __future__ import annotations

import json
import importlib.util
import shlex
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(REPO))
from agents.common.hooks.hook_manifest import HOOK_SPECS  # noqa: E402
from install import (
    _dir_is_writable,
    _foreign_files,
    _install_specs,
    CODEX_AGGRESSIVE_BUDGET_OVERRIDE,
    CODEX_BALANCED_BUDGET_OVERRIDE,
    apply_codex_savings_profile,
    build_codex_hook_entries,
    codex_agents_fragment,
    copy_tree,
    handle_agents_md,
    handle_search_config,
    launcher_rel,
    wire_codex_hooks_json,
    unwire_codex_hooks_json,
    write_codex_tool_shims,
    write_python_launcher,
)

FRAGMENT = REPO / "agents" / "codex" / "instructions" / "AGENTS.md.fragment"


# ---------------------------------------------------------------------------
# Directory structure
# ---------------------------------------------------------------------------

class TestCodexInstallDirStructure:
    def test_less_tokens_tools_shims_created(self, tmp_path):
        changed = write_codex_tool_shims(
            REPO / ".claude" / "tools",
            tmp_path,
            force=True,
            overwrite_modified=True,
        )
        tools_dir = tmp_path / ".less_tokens" / "tools"
        assert changed > 0
        assert tools_dir.is_dir()
        assert (tools_dir / "search.py").exists()
        assert (tools_dir / "embeddings.py").exists()
        assert "Codex compatibility shim" in (tools_dir / "search.py").read_text()

    def test_less_tokens_schema_created(self, tmp_path):
        copy_tree(
            REPO / ".claude" / "schema",
            tmp_path / ".less_tokens" / "schema",
            tmp_path,
            force=True, overwrite_modified=True, label=".less_tokens/schema/",
        )
        assert (tmp_path / ".less_tokens" / "schema").is_dir()

    def test_less_tokens_hooks_created(self, tmp_path):
        copy_tree(
            REPO / "agents" / "common" / "hooks",
            tmp_path / ".less_tokens" / "hooks",
            tmp_path,
            force=True, overwrite_modified=True, label=".less_tokens/hooks/",
        )
        assert (tmp_path / ".less_tokens" / "hooks" / "payload.py").exists()
        assert (tmp_path / ".less_tokens" / "hooks" / "search_first.py").exists()

    def test_codex_python_launcher_created(self, tmp_path):
        venv_py = tmp_path / ".venv" / "bin" / "python"
        venv_py.parent.mkdir(parents=True)
        venv_py.write_text("#!/bin/sh\n", encoding="utf-8")

        changed = write_python_launcher(tmp_path, launcher_rel("codex"), venv_py)

        launcher = tmp_path / ".less_tokens" / "bin" / "python"
        assert changed == 2
        assert launcher.exists()
        assert ".venv/bin/python" in launcher.read_text(encoding="utf-8")
        assert (tmp_path / ".less_tokens" / "bin" / "python.cmd").exists()

    def test_codex_python_launcher_dry_run_writes_nothing(self, tmp_path):
        venv_py = tmp_path / ".venv" / "bin" / "python"
        changed = write_python_launcher(tmp_path, launcher_rel("codex"), venv_py, dry_run=True)

        assert changed == 2
        assert not (tmp_path / ".less_tokens" / "bin" / "python").exists()
        assert not (tmp_path / ".less_tokens" / "bin" / "python.cmd").exists()

    def test_codex_specs_exclude_claude_hooks(self):
        specs = _install_specs(caveman=False, agents={"codex"})
        dest_dirs = [s[1] for s in specs]
        assert ".claude/hooks" not in dest_dirs

    def test_search_config_shim_written_to_less_tokens(self, tmp_path):
        write_codex_tool_shims(REPO / ".claude" / "tools", tmp_path, force=True, overwrite_modified=True)
        config_text = (tmp_path / ".less_tokens" / "tools" / "search_config.py").read_text()
        assert "Codex compatibility shim" in config_text
        assert 'LESS_TOKENS_AGENT", "codex"' in config_text

    def test_search_config_source_of_truth_stays_claude_tools(self, tmp_path):
        handle_search_config(
            REPO / ".claude" / "tools" / "search_config.py",
            tmp_path / ".claude" / "tools" / "search_config.py",
            tmp_path,
            False, False,
        )
        assert not (tmp_path / ".less_tokens" / "tools" / "search_config.py").exists()
        assert "_STATE_AGENT_AWARE" in (tmp_path / ".claude" / "tools" / "search_config.py").read_text()

    def test_generated_tool_shim_imports_and_executes_real_tool(self, tmp_path):
        real_tools = tmp_path / ".claude" / "tools"
        real_tools.mkdir(parents=True)
        (real_tools / "demo.py").write_text(
            "import os\n"
            "VALUE = os.environ.get('LESS_TOKENS_AGENT')\n"
            "if __name__ == '__main__':\n"
            "    print(VALUE)\n"
        )

        write_codex_tool_shims(real_tools, tmp_path, force=True, overwrite_modified=True)
        shim = tmp_path / ".less_tokens" / "tools" / "demo.py"

        spec = importlib.util.spec_from_file_location("_demo_shim", shim)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert mod.VALUE == "codex"

        result = subprocess.run([sys.executable, str(shim)], capture_output=True, text=True)
        assert result.returncode == 0
        assert result.stdout.strip() == "codex"


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

    def test_codex_hook_runtime_helper_copied(self, tmp_path):
        changed = copy_tree(
            REPO / "agents" / "codex" / "hooks",
            tmp_path / ".codex" / "hooks",
            tmp_path,
            force=True, overwrite_modified=True, label=".codex/hooks/",
        )
        assert changed > 0
        assert (tmp_path / ".codex" / "hooks" / "_codex_runtime.py").exists()

    def test_dir_is_writable_helper_on_existing_dir(self, tmp_path):
        d = tmp_path / "sub"
        d.mkdir()
        assert _dir_is_writable(tmp_path, "sub")

    def test_dir_is_writable_helper_on_missing_dir(self, tmp_path):
        assert _dir_is_writable(tmp_path, "nonexistent")


# ---------------------------------------------------------------------------
# Hook entry construction
# ---------------------------------------------------------------------------

class TestBuildCodexHookEntries:
    def test_core_entries_use_absolute_codex_launcher_and_agent_env(self, tmp_path):
        entries = build_codex_hook_entries(
            tmp_path / ".venv" / "bin" / "python",
            tmp_path,
            Namespace(truncate=False, compact=False, caveman=False),
        )
        commands = [cmd for _, _, cmd in entries]
        launcher = (tmp_path / ".less_tokens" / "bin" / ("python.cmd" if sys.platform == "win32" else "python")).resolve().as_posix()
        hooks_dir = str((tmp_path / ".codex" / "hooks").resolve())
        assert len(entries) == sum(len(spec.codex) for spec in HOOK_SPECS)
        assert all(cmd.startswith(f"LESS_TOKENS_AGENT=codex {launcher}") for cmd in commands)
        assert all(hooks_dir in cmd for cmd in commands)
        assert all(" .less_tokens/bin/python" not in cmd for cmd in commands)
        assert all(" .codex/hooks/" not in cmd for cmd in commands)
        assert any("budget-observer.py" in cmd for cmd in commands)
        assert any("search-first.py" in cmd for cmd in commands)
        assert any("read-guard.py" in cmd for cmd in commands)
        assert any("auto-slice.py" in cmd for cmd in commands)
        assert any("grep-first-read.py" in cmd for cmd in commands)
        assert any("read-after-edit.py" in cmd for cmd in commands)
        assert any("context-cache.py" in cmd for cmd in commands)
        assert any("listing-guard.py" in cmd for cmd in commands)
        assert any("lean-output.py" in cmd for cmd in commands)
        assert any("post-edit-diff.py" in cmd for cmd in commands)
        assert any("index-refresh.py" in cmd for cmd in commands)
        assert any("agentsmd-budget.py" in cmd for cmd in commands)
        assert any("savings-html.py" in cmd for cmd in commands)
        assert any("truncate-output.py" in cmd for cmd in commands)
        assert any("compact-trigger.py" in cmd for cmd in commands)
        assert any("terse-reminder.py" in cmd for cmd in commands)

    def test_explicit_optional_flags_are_back_compat_no_op(self, tmp_path):
        default = build_codex_hook_entries(
            tmp_path / ".venv" / "bin" / "python",
            tmp_path,
            Namespace(truncate=False, compact=False, caveman=False),
        )
        entries = build_codex_hook_entries(
            tmp_path / ".venv" / "bin" / "python",
            tmp_path,
            Namespace(truncate=True, compact=True, caveman=True),
        )
        assert entries == default

    def test_codex_optional_hooks_can_opt_out(self, tmp_path):
        entries = build_codex_hook_entries(
            tmp_path / ".venv" / "bin" / "python",
            tmp_path,
            Namespace(
                truncate=False,
                compact=False,
                caveman=False,
                no_truncate=True,
                no_compact=True,
                no_caveman=True,
            ),
        )
        commands = [cmd for _, _, cmd in entries]
        assert not any("truncate-output.py" in cmd for cmd in commands)
        assert not any("compact-trigger.py" in cmd for cmd in commands)
        assert not any("terse-reminder.py" in cmd for cmd in commands)

    def test_aggressive_profile_marks_hook_commands(self, tmp_path):
        entries = build_codex_hook_entries(
            tmp_path / ".venv" / "bin" / "python",
            tmp_path,
            Namespace(
                truncate=False,
                compact=False,
                caveman=False,
                codex_savings="aggressive",
            ),
        )
        commands = [cmd for _, _, cmd in entries]
        assert commands
        assert all("LESS_TOKENS_CODEX_SAVINGS=aggressive" in cmd for cmd in commands)

    def test_aggressive_profile_enables_optional_hooks_despite_opt_outs(self, tmp_path):
        entries = build_codex_hook_entries(
            tmp_path / ".venv" / "bin" / "python",
            tmp_path,
            Namespace(
                truncate=False,
                compact=False,
                caveman=False,
                no_truncate=True,
                no_compact=True,
                no_caveman=True,
                codex_savings="aggressive",
            ),
        )
        commands = [cmd for _, _, cmd in entries]
        assert any("truncate-output.py" in cmd for cmd in commands)
        assert any("compact-trigger.py" in cmd for cmd in commands)
        assert any("terse-reminder.py" in cmd for cmd in commands)

    @pytest.mark.skipif(sys.platform == "win32", reason="Codex hook env prefix is POSIX shell syntax")
    def test_generated_hook_command_runs_from_nested_cwd(self, tmp_path):
        entries = build_codex_hook_entries(
            tmp_path / ".venv" / "bin" / "python",
            tmp_path,
            Namespace(truncate=False, compact=False, caveman=False),
        )
        command = next(cmd for _, _, cmd in entries if "savings-html.py" in cmd)

        launcher = tmp_path / ".less_tokens" / "bin" / "python"
        launcher.parent.mkdir(parents=True)
        launcher.write_text(f"#!/bin/sh\nexec {shlex.quote(sys.executable)} \"$@\"\n", encoding="utf-8")
        launcher.chmod(0o755)

        hook = tmp_path / ".codex" / "hooks" / "savings-html.py"
        hook.parent.mkdir(parents=True)
        hook.write_text("import os\nprint(os.environ.get('LESS_TOKENS_AGENT'))\n", encoding="utf-8")

        nested = tmp_path / "subdir"
        nested.mkdir()
        result = subprocess.run(
            command,
            cwd=nested,
            input="{}",
            shell=True,
            capture_output=True,
            text=True,
            timeout=5,
        )

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "codex"


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

    def test_agents_md_points_to_less_tokens_skill(self, tmp_path):
        handle_agents_md(FRAGMENT, tmp_path)
        content = (tmp_path / "AGENTS.md").read_text()
        assert "large or indexed files" in content
        assert "use the `less-tokens` skill" in content
        assert "search.py" not in content

    def test_agents_md_dry_run_does_not_write(self, tmp_path):
        handle_agents_md(FRAGMENT, tmp_path, dry_run=True)
        assert not (tmp_path / "AGENTS.md").exists()

    def test_agents_md_updates_existing_managed_block(self, tmp_path):
        agents_md = tmp_path / "AGENTS.md"
        agents_md.write_text("Intro\n\n<!-- less_tokens: begin -->\nold\n<!-- less_tokens: end -->\n")
        handle_agents_md(FRAGMENT, tmp_path)
        content = agents_md.read_text()
        assert "Intro" in content
        assert "old" not in content
        assert "Token Discipline" in content

    def test_balanced_agents_fragment_matches_source(self):
        source = FRAGMENT.read_text(encoding="utf-8").strip()
        assert codex_agents_fragment(source, "balanced") == source

    def test_aggressive_agents_fragment_adds_profile_note(self):
        source = FRAGMENT.read_text(encoding="utf-8")
        fragment = codex_agents_fragment(source, "aggressive")
        assert "Token Discipline" in fragment
        assert "Aggressive Codex savings" in fragment


# ---------------------------------------------------------------------------
# Codex savings profile
# ---------------------------------------------------------------------------

class TestCodexSavingsProfile:
    def test_balanced_profile_writes_current_codex_budget_override(self, tmp_path):
        config_dir = tmp_path / ".less_tokens" / "config"
        config_dir.mkdir(parents=True)
        (config_dir / "budget.json").write_text(
            json.dumps({"agent_overrides": {"claude": {}, "codex": {}}}),
            encoding="utf-8",
        )

        changed = apply_codex_savings_profile(tmp_path, "balanced")

        data = json.loads((config_dir / "budget.json").read_text(encoding="utf-8"))
        assert changed == 1
        assert data["agent_overrides"]["codex"] == CODEX_BALANCED_BUDGET_OVERRIDE
        assert data["agent_overrides"]["claude"] == {}

    def test_aggressive_profile_only_changes_codex_override(self, tmp_path):
        config_dir = tmp_path / ".less_tokens" / "config"
        config_dir.mkdir(parents=True)
        (config_dir / "budget.json").write_text(
            json.dumps({
                "mode": "advise",
                "agent_overrides": {
                    "claude": {"hard_caps": {"single_tool_output": 1111}},
                    "codex": CODEX_BALANCED_BUDGET_OVERRIDE,
                },
            }),
            encoding="utf-8",
        )

        changed = apply_codex_savings_profile(tmp_path, "aggressive")

        data = json.loads((config_dir / "budget.json").read_text(encoding="utf-8"))
        assert changed == 1
        assert data["mode"] == "advise"
        assert data["agent_overrides"]["claude"] == {"hard_caps": {"single_tool_output": 1111}}
        assert data["agent_overrides"]["codex"] == CODEX_AGGRESSIVE_BUDGET_OVERRIDE

    def test_profile_write_is_idempotent(self, tmp_path):
        config_dir = tmp_path / ".less_tokens" / "config"
        config_dir.mkdir(parents=True)
        (config_dir / "budget.json").write_text(
            json.dumps({"agent_overrides": {"codex": CODEX_AGGRESSIVE_BUDGET_OVERRIDE}}),
            encoding="utf-8",
        )

        assert apply_codex_savings_profile(tmp_path, "aggressive") == 0


# ---------------------------------------------------------------------------
# wire_codex_hooks_json / unwire_codex_hooks_json
# ---------------------------------------------------------------------------

class TestWireCodexHooksJson:
    def test_malformed_hooks_json_is_replaced(self, tmp_path):
        hooks_json = tmp_path / ".codex" / "hooks.json"
        hooks_json.parent.mkdir(parents=True)
        hooks_json.write_text("{not json")
        added, present = wire_codex_hooks_json(
            hooks_json,
            [("PostToolUse", "Edit", "python index-refresh.py")],
        )
        assert (added, present) == (1, 0)
        assert json.loads(hooks_json.read_text())["hooks"][0]["matcher"] == "Edit"

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

    def test_unwire_missing_or_malformed_hooks_json_returns_zero(self, tmp_path):
        hooks_json = tmp_path / ".codex" / "hooks.json"
        assert unwire_codex_hooks_json(hooks_json, REPO, dry_run=False) == 0

        hooks_json.parent.mkdir(parents=True)
        hooks_json.write_text("{not json")
        assert unwire_codex_hooks_json(hooks_json, REPO, dry_run=False) == 0

    def test_unwire_non_list_hooks_returns_zero(self, tmp_path):
        hooks_json = tmp_path / ".codex" / "hooks.json"
        hooks_json.parent.mkdir(parents=True)
        hooks_json.write_text(json.dumps({"hooks": {"PostToolUse": []}}))
        assert unwire_codex_hooks_json(hooks_json, REPO, dry_run=False) == 0


# ---------------------------------------------------------------------------
# Collision detection
# ---------------------------------------------------------------------------

class TestCodexForeignFiles:
    def test_foreign_files_ignores_hidden_tool_dirs(self, tmp_path):
        tools = tmp_path / ".claude" / "tools"
        tools.mkdir(parents=True)
        (tools / "host_owned.py").write_text("# not ours\n")

        assert _foreign_files(REPO, tmp_path, caveman=False, agents={"codex"}) == []

    def test_foreign_files_returns_empty_after_install_state_exists(self, tmp_path):
        state = tmp_path / ".claude" / "state" / "install.json"
        state.parent.mkdir(parents=True)
        state.write_text("{}")

        assert _foreign_files(REPO, tmp_path, caveman=False, agents={"codex"}) == []

    def test_foreign_files_ignores_shared_hook_dirs(self, tmp_path):
        hooks = tmp_path / ".less_tokens" / "hooks"
        hooks.mkdir(parents=True)
        (hooks / "host_hook.py").write_text("# allowed\n")

        assert _foreign_files(REPO, tmp_path, caveman=False, agents={"codex"}) == []
