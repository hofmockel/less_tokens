"""PT9: `_codex_runtime.venv_python()` must pick the platform-correct launcher.

install.py's write_python_launcher() always writes both a POSIX shell script
at .less_tokens/bin/python and a Windows sibling at .less_tokens/bin/python.cmd
(agents_codex_hooks listing-guard.py/lean-output.py/index-refresh.py used to
hardcode the bare, extensionless path with no platform check — on Windows
that file exists but is a POSIX shell script, not a valid Win32 executable,
so subprocess.run([bare_path, ...]) raised WinError 193 the first time CI
ever generated a real .less_tokens/ install (see CHANGELOG.md PT9)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "agents" / "codex" / "hooks"))

from _codex_runtime import venv_python  # noqa: E402


def test_picks_windows_cmd_sibling_when_present(tmp_path, monkeypatch):
    bare = tmp_path / ".less_tokens" / "bin" / "python"
    cmd = bare.with_suffix(".cmd")
    bare.parent.mkdir(parents=True)
    bare.write_text("#!/bin/sh\n")
    cmd.write_text("@echo off\r\n")

    monkeypatch.setattr(sys, "platform", "win32")
    assert venv_python(tmp_path) == cmd


def test_picks_bare_posix_launcher_on_non_windows(tmp_path, monkeypatch):
    bare = tmp_path / ".less_tokens" / "bin" / "python"
    bare.parent.mkdir(parents=True)
    bare.write_text("#!/bin/sh\n")

    monkeypatch.setattr(sys, "platform", "darwin")
    assert venv_python(tmp_path) == bare


def test_falls_back_to_sys_executable_when_no_launcher_installed(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    assert venv_python(tmp_path) == Path(sys.executable)

    monkeypatch.setattr(sys, "platform", "linux")
    assert venv_python(tmp_path) == Path(sys.executable)


def test_does_not_pick_bare_posix_launcher_on_windows_even_if_only_bare_exists(tmp_path, monkeypatch):
    """The bug this regression test pins: a bare .less_tokens/bin/python existing
    must never be handed to subprocess.run on Windows just because it exists."""
    bare = tmp_path / ".less_tokens" / "bin" / "python"
    bare.parent.mkdir(parents=True)
    bare.write_text("#!/bin/sh\n")

    monkeypatch.setattr(sys, "platform", "win32")
    result = venv_python(tmp_path)
    assert result != bare
    assert result == Path(sys.executable)
