"""Regression: index-refresh must detach the background refresh per-platform.

`subprocess.Popen(..., start_new_session=True)` is POSIX-only. On Windows the
kwarg is silently ignored, so the spawned `embeddings.py refresh` child stays
attached to the Claude Code process instead of detaching — defeating the
fire-and-forget intent of the hook.

The fix branches on `sys.platform`: POSIX keeps `start_new_session=True`;
Windows passes `creationflags=DETACHED_PROCESS|CREATE_NEW_PROCESS_GROUP`
instead. These tests pin both kwarg shapes and assert `check_index_refresh`
forwards the platform-correct kwargs into `Popen`.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

import agents.common.hooks.index_refresh as index_refresh_mod
from agents.common.hooks.payload import normalize_claude

_DETACHED = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)


@pytest.fixture()
def index_refresh():
    return index_refresh_mod


class TestDetachKwargs:
    def test_linux_uses_start_new_session(self, index_refresh):
        assert index_refresh._detach_kwargs("linux") == {"start_new_session": True}

    def test_darwin_uses_start_new_session(self, index_refresh):
        assert index_refresh._detach_kwargs("darwin") == {"start_new_session": True}

    def test_windows_uses_creationflags_not_session(self, index_refresh):
        kwargs = index_refresh._detach_kwargs("win32")
        assert "start_new_session" not in kwargs
        assert "creationflags" in kwargs
        assert kwargs["creationflags"] & _DETACHED == _DETACHED


class TestMainForwardsDetach:
    def _drive(self, mod, monkeypatch, platform, tmp_path):
        captured: dict = {}

        def fake_popen(*args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs
            return object()

        monkeypatch.setattr(mod.subprocess, "Popen", fake_popen)
        monkeypatch.setattr(mod.sys, "platform", platform)
        monkeypatch.setattr(mod, "is_indexed", lambda *_a, **_kw: True)

        tools_dir = tmp_path / ".claude" / "tools"
        tools_dir.mkdir(parents=True)
        (tools_dir / "embeddings.py").touch()
        state_dir = tmp_path / ".claude" / "state"
        state_dir.mkdir(parents=True)

        payload = normalize_claude({
            "tool_name": "Write",
            "tool_input": {"file_path": str(tools_dir / "x.py")},
        })
        config = {
            "venv_py": Path(sys.executable),
            "tool_prefix": ".claude/tools",
            "root_globs": ("*.md", "*.py", "*.sql"),
        }
        code, _, _ = mod.check_index_refresh(
            payload, repo=tmp_path, state_dir=state_dir, config=config
        )
        assert code == 0
        return captured

    def test_windows_main_passes_creationflags(self, index_refresh, monkeypatch, tmp_path):
        captured = self._drive(index_refresh, monkeypatch, "win32", tmp_path)
        assert "start_new_session" not in captured["kwargs"]
        assert captured["kwargs"]["creationflags"] & _DETACHED == _DETACHED

    def test_posix_main_passes_start_new_session(self, index_refresh, monkeypatch, tmp_path):
        captured = self._drive(index_refresh, monkeypatch, "linux", tmp_path)
        assert captured["kwargs"].get("start_new_session") is True
        assert "creationflags" not in captured["kwargs"]
