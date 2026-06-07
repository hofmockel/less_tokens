"""Bug 16: create_venv used hardcoded 'python3' instead of sys.executable.

The hardcoded string fails when python3 is not on PATH or when a different
Python version should be used (e.g. python3.12 vs python3.11). Using
sys.executable guarantees the venv is created with the same interpreter that
ran install.py.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
import install  # noqa: E402


def test_create_venv_uses_sys_executable(tmp_path, monkeypatch):
    calls: list[list[str]] = []

    def fake_check_call(cmd, **kw):
        calls.append([str(c) for c in cmd])
        target = Path(cmd[-1])
        target.mkdir(parents=True, exist_ok=True)
        (target / "bin").mkdir(parents=True, exist_ok=True)
        (target / "bin" / "python").write_text("")
        (target / "bin" / "python").chmod(0o755)
        return 0

    monkeypatch.setattr(subprocess, "check_call", fake_check_call)
    install.create_venv(tmp_path)
    assert calls, "check_call was never invoked"
    assert calls[0][0] == sys.executable, (
        f"create_venv should use sys.executable ({sys.executable!r}), "
        f"got {calls[0][0]!r}"
    )
