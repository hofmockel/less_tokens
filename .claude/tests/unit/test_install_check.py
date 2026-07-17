"""Tests for install.py do_check (--check flag)."""
from __future__ import annotations

import argparse
import json
import shlex
import sqlite3
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from install import _CODEX_TOOL_SHIM_MARKER, build_codex_hook_entries, do_check


def _args(**kwargs) -> argparse.Namespace:
    defaults = {"agent": "claude", "local": False}
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def _minimal_install(tmp_path: Path, venv_py: Path | None = None) -> Path:
    """Build a minimal valid install layout under tmp_path."""
    venv_py = venv_py or (tmp_path / "fake_venv" / "bin" / "python")
    venv_py.parent.mkdir(parents=True, exist_ok=True)
    venv_py.touch()

    tools = tmp_path / ".claude" / "tools"
    tools.mkdir(parents=True)

    config = tools / "search_config.py"
    config.write_text(f'VENV_PY = {repr(venv_py.as_posix())}\n')

    hooks = tmp_path / ".claude" / "hooks"
    hooks.mkdir(parents=True)
    (hooks / "search-first.py").touch()

    db = tmp_path / ".claude" / "index.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE chunks (id INTEGER PRIMARY KEY, body TEXT)")
    conn.execute("INSERT INTO chunks (body) VALUES ('hello')")
    conn.commit()
    conn.close()

    settings = tmp_path / ".claude" / "settings.json"
    settings.write_text(json.dumps({
        "hooks": {"PreToolUse": [{"matcher": "Read", "hooks": [{"type": "command", "command": "python hook.py"}]}]}
    }))

    budget_config = tmp_path / ".less_tokens" / "config"
    budget_config.mkdir(parents=True)
    (budget_config / "budget.json").write_text(json.dumps({
        "version": 2,
        "categories": {"session_summary": 3000},
    }))

    budget_pkg = tmp_path / ".less_tokens" / "hooks" / "budget"
    budget_pkg.mkdir(parents=True)
    (budget_pkg / "__init__.py").write_text("")

    budget_tools = tmp_path / ".less_tokens" / "tools"
    budget_tools.mkdir(parents=True)
    (budget_tools / "budget_report.py").write_text("#!/usr/bin/env python3\n")
    (budget_tools / "budget_doctor.py").write_text("#!/usr/bin/env python3\n")

    return tmp_path


def _minimal_codex_install(tmp_path: Path) -> Path:
    root = _minimal_install(tmp_path)
    venv_py = root / "fake_venv" / "bin" / "python"

    launcher_name = "python.exe" if sys.platform == "win32" else "python"
    launcher = root / ".less_tokens" / "bin" / launcher_name
    launcher.parent.mkdir(parents=True)
    launcher.write_text("#!/bin/sh\n")

    codex_tools = root / ".less_tokens" / "tools"
    codex_tools.mkdir(parents=True, exist_ok=True)
    (codex_tools / "search_config.py").write_text(f"{_CODEX_TOOL_SHIM_MARKER}\n")

    codex_hooks = root / ".codex" / "hooks"
    codex_hooks.mkdir(parents=True)
    entries = build_codex_hook_entries(venv_py, root, _args(agent="codex"))
    for _, _, cmd in entries:
        (codex_hooks / Path(shlex.split(cmd)[-1]).name).touch()
    (root / ".codex" / "hooks.json").write_text(json.dumps({
        "hooks": [
            {"event": ev, "matcher": matcher, "command": cmd}
            for ev, matcher, cmd in entries
        ]
    }))

    (root / "AGENTS.md").write_text(
        "<!-- less_tokens: begin -->\n## Token Discipline\n<!-- less_tokens: end -->\n"
    )
    return root


def _successful_codex_check_run(command, **kwargs):
    """Model the real truncation hook contract for do_check subprocess mocks."""
    result = subprocess.CompletedProcess(command, 0, stdout="", stderr="")
    if command and str(command[-1]).endswith("truncate-output.py"):
        payload = json.loads(kwargs["input"])
        output = payload.get("tool_response", "")
        cap = int(kwargs["env"]["LESS_TOKENS_CODEX_MAX_TOOL_OUTPUT_CHARS"])
        if len(output) > cap:
            result.returncode = 2
            result.stdout = "smoke-head\n[... 7,700 chars omitted ...]\nsmoke-tail\n"
            result.stderr = "[truncated — 7,700 chars omitted (8,214 total)]\n"
    return result


class TestDoCheckAllPass:
    def test_returns_0_on_valid_install(self, tmp_path, capsys):
        root = _minimal_install(tmp_path)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            rc = do_check(root, _args())
        assert rc == 0
        out = capsys.readouterr().out
        assert "[✗]" not in out
        assert "All checks passed" in out

    def test_returns_0_on_valid_codex_install(self, tmp_path, capsys):
        root = _minimal_codex_install(tmp_path)
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = _successful_codex_check_run
            rc = do_check(root, _args(agent="codex"))
        assert rc == 0
        out = capsys.readouterr().out
        assert "[✗]" not in out
        assert ".codex/hooks.json has all" in out
        assert "AGENTS.md contains managed less_tokens block" in out
        assert ".less_tokens/config/budget.json present" in out
        assert "Codex hook wrappers run from nested cwd" in out
        hook_calls = [
            call for call in mock_run.call_args_list
            if call.args and str(root / ".codex" / "hooks") in str(call.args[0])
        ]
        assert len(hook_calls) == 3
        for call in hook_calls:
            expected_cwd = root / ".less_tokens" / "tools"
            assert call.kwargs["cwd"] == str(expected_cwd)
            assert call.kwargs["env"]["LESS_TOKENS_AGENT"] == "codex"

        truncate_call = next(
            call for call in hook_calls
            if str(call.args[0][-1]).endswith("truncate-output.py")
        )
        payload = json.loads(truncate_call.kwargs["input"])
        assert "tool_output" not in payload
        assert payload["tool_response"].startswith("smoke-head\n")
        assert payload["tool_response"].endswith("\nsmoke-tail\n")
        assert len(payload["tool_response"]) > int(
            truncate_call.kwargs["env"]["LESS_TOKENS_CODEX_MAX_TOOL_OUTPUT_CHARS"]
        )

    def test_fails_when_codex_truncation_smoke_does_not_truncate(self, tmp_path, capsys):
        root = _minimal_codex_install(tmp_path)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess([], 0, stdout="", stderr="")
            rc = do_check(root, _args(agent="codex"))
        assert rc == 1
        assert "truncate-output.py failed from nested cwd" in capsys.readouterr().out

    def test_codex_check_does_not_require_claude_hooks(self, tmp_path, capsys):
        root = _minimal_codex_install(tmp_path)
        import shutil
        shutil.rmtree(root / ".claude" / "hooks")
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = _successful_codex_check_run
            rc = do_check(root, _args(agent="codex"))
        assert rc == 0
        out = capsys.readouterr().out
        assert ".codex/hooks.json has all" in out
        assert ".claude/hooks/ missing" not in out

    def test_search_config_load_supports_file_dunder(self, tmp_path, capsys):
        root = _minimal_install(tmp_path)
        venv_py = root / "fake_venv" / "bin" / "python"
        (root / ".claude" / "tools" / "search_config.py").write_text(
            "from pathlib import Path\n"
            "ROOT = Path(__file__).resolve().parent\n"
            f"VENV_PY = {repr(venv_py.as_posix())}\n"
        )
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            rc = do_check(root, _args())
        assert rc == 0
        assert "Could not load search_config.py" not in capsys.readouterr().out


class TestDoCheckBudgetControlPlane:
    def test_fails_when_budget_config_absent(self, tmp_path, capsys):
        root = _minimal_install(tmp_path)
        (root / ".less_tokens" / "config" / "budget.json").unlink()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            rc = do_check(root, _args())
        assert rc == 1
        assert "budget.json missing" in capsys.readouterr().out

    def test_fails_when_budget_package_absent(self, tmp_path, capsys):
        root = _minimal_install(tmp_path)
        (root / ".less_tokens" / "hooks" / "budget" / "__init__.py").unlink()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            rc = do_check(root, _args())
        assert rc == 1
        assert "budget package missing" in capsys.readouterr().out

    def test_fails_when_budget_doctor_absent(self, tmp_path, capsys):
        root = _minimal_install(tmp_path)
        (root / ".less_tokens" / "tools" / "budget_doctor.py").unlink()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            rc = do_check(root, _args())
        assert rc == 1
        assert "budget_doctor.py missing" in capsys.readouterr().out


class TestDoCheckVenvMissing:
    def test_fails_when_search_config_absent(self, tmp_path, capsys):
        rc = do_check(tmp_path, _args())
        assert rc == 1
        assert "search_config.py missing" in capsys.readouterr().out

    def test_fails_when_venv_py_path_missing(self, tmp_path, capsys):
        tools = tmp_path / ".claude" / "tools"
        tools.mkdir(parents=True)
        (tools / "search_config.py").write_text('VENV_PY = "/nonexistent/python"\n')
        rc = do_check(tmp_path, _args())
        assert rc == 1
        assert "VENV_PY missing" in capsys.readouterr().out


class TestDoCheckIndex:
    def test_fails_when_index_db_absent(self, tmp_path, capsys):
        root = _minimal_install(tmp_path)
        (root / ".claude" / "index.db").unlink()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            rc = do_check(root, _args())
        assert rc == 1
        assert "index.db missing" in capsys.readouterr().out

    def test_fails_when_index_db_empty(self, tmp_path, capsys):
        root = _minimal_install(tmp_path)
        db = root / ".claude" / "index.db"
        with sqlite3.connect(str(db)) as conn:
            conn.execute("DELETE FROM chunks")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            rc = do_check(root, _args())
        assert rc == 1
        assert "0 chunks" in capsys.readouterr().out


class TestDoCheckHooks:
    def test_fails_when_hooks_dir_absent(self, tmp_path, capsys):
        root = _minimal_install(tmp_path)
        import shutil
        shutil.rmtree(root / ".claude" / "hooks")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            rc = do_check(root, _args())
        assert rc == 1
        assert "hooks/ missing" in capsys.readouterr().out

    def test_fails_when_hooks_dir_empty(self, tmp_path, capsys):
        root = _minimal_install(tmp_path)
        for f in (root / ".claude" / "hooks").glob("*.py"):
            f.unlink()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            rc = do_check(root, _args())
        assert rc == 1
        assert "no .py scripts" in capsys.readouterr().out


class TestDoCheckSettings:
    def test_fails_when_settings_absent(self, tmp_path, capsys):
        root = _minimal_install(tmp_path)
        (root / ".claude" / "settings.json").unlink()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            rc = do_check(root, _args())
        assert rc == 1
        assert "settings.json missing" in capsys.readouterr().out

    def test_fails_when_settings_has_no_hooks(self, tmp_path, capsys):
        root = _minimal_install(tmp_path)
        (root / ".claude" / "settings.json").write_text(json.dumps({"hooks": {}}))
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            rc = do_check(root, _args())
        assert rc == 1
        assert "no hooks" in capsys.readouterr().out

    def test_local_flag_checks_settings_local_json(self, tmp_path, capsys):
        root = _minimal_install(tmp_path)
        local = root / ".claude" / "settings.local.json"
        local.write_text(json.dumps({
            "hooks": {"PreToolUse": [{"matcher": "Read", "hooks": [{"type": "command", "command": "python hook.py"}]}]}
        }))
        (root / ".claude" / "settings.json").unlink()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            rc = do_check(root, _args(local=True))
        assert rc == 0


class TestDoCheckSmokeQuery:
    def test_fails_when_search_py_returns_nonzero(self, tmp_path, capsys):
        root = _minimal_install(tmp_path)
        search_py = root / ".claude" / "tools" / "search.py"
        search_py.write_text("")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            mock_run.return_value.stderr = "boom"
            rc = do_check(root, _args())
        assert rc == 1
        assert "smoke query failed" in capsys.readouterr().out
