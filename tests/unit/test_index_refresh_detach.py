"""Regression: index-refresh.py must detach the background refresh per-platform.

`subprocess.Popen(..., start_new_session=True)` is POSIX-only. On Windows the
kwarg is silently ignored, so the spawned `embeddings.py refresh` child stays
attached to the Claude Code process instead of detaching - defeating the
fire-and-forget intent of the hook.

The fix branches on `sys.platform`: POSIX keeps `start_new_session=True`;
Windows passes `creationflags=DETACHED_PROCESS|CREATE_NEW_PROCESS_GROUP`
instead. These tests pin both kwarg shapes and assert `main()` actually
forwards the platform-correct kwargs into `Popen`.
"""
from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

from tests.conftest import REPO_ROOT, load_hook

_DETACHED = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)


@pytest.fixture()
def index_refresh(tmp_path):
    mod = load_hook(REPO_ROOT / "hooks" / "index-refresh.py")
    mod.REPO = tmp_path
    return mod


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
    def _drive(self, mod, monkeypatch, platform):
        captured: dict = {}

        def fake_popen(*args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs
            return object()

        monkeypatch.setattr(mod.subprocess, "Popen", fake_popen)
        monkeypatch.setattr(mod.sys, "platform", platform)
        monkeypatch.setattr(mod, "is_indexed", lambda _p: True)
        monkeypatch.setattr(mod, "VENV_PY", Path(sys.executable))
        payload = json.dumps(
            {
                "tool_name": "Write",
                "tool_input": {"file_path": str(mod.REPO / "tools" / "x.py")},
            }
        )
        monkeypatch.setattr(mod.sys, "stdin", io.StringIO(payload))
        assert mod.main() == 0
        return captured

    def test_windows_main_passes_creationflags(self, index_refresh, monkeypatch):
        captured = self._drive(index_refresh, monkeypatch, "win32")
        assert "start_new_session" not in captured["kwargs"]
        assert captured["kwargs"]["creationflags"] & _DETACHED == _DETACHED

    def test_posix_main_passes_start_new_session(self, index_refresh, monkeypatch):
        captured = self._drive(index_refresh, monkeypatch, "linux")
        assert captured["kwargs"].get("start_new_session") is True
        assert "creationflags" not in captured["kwargs"]
