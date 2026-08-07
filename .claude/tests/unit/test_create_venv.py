"""Installer can create .claude/.venv-tokens in a single pass.

Without `--create-venv`, a missing venv aborts the install with an
instruction to run `python3 -m venv .venv` and re-invoke — a two-step
dance. The new flag does the venv creation inline inside .claude/.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
import install  # noqa: E402


def test_create_venv_flag_is_exposed():
    src = (REPO / "install.py").read_text()
    assert "--create-venv" in src


def test_create_venv_helper_runs_python_m_venv(tmp_path, monkeypatch):
    calls: list[list[str]] = []

    def fake_check_call(cmd, **kw):
        calls.append([str(c) for c in cmd])
        # Simulate venv creation by laying down the python binary.
        target = Path(cmd[-1])
        target.mkdir(parents=True, exist_ok=True)
        (target / "bin").mkdir(parents=True, exist_ok=True)
        (target / "bin" / "python").write_text("")
        (target / "bin" / "python").chmod(0o755)
        (target / "Scripts").mkdir(parents=True, exist_ok=True)
        (target / "Scripts" / "python.exe").write_text("")
        return 0

    monkeypatch.setattr(subprocess, "check_call", fake_check_call)
    venv_dir = install.create_venv(tmp_path)
    assert venv_dir == tmp_path / ".claude" / ".venv-tokens"
    assert calls and calls[0][1:3] == ["-m", "venv"]
    assert calls[0][-1].endswith(".venv-tokens")
    assert install.venv_python(venv_dir).exists()


def test_create_venv_helper_refuses_when_target_exists(tmp_path):
    (tmp_path / ".claude" / ".venv-tokens").mkdir(parents=True)
    # Should not clobber an existing directory — raise instead of
    # quietly recreating, since a pre-existing path may be a partial
    # venv we don't want to overwrite.
    try:
        install.create_venv(tmp_path)
    except FileExistsError:
        return
    raise AssertionError("create_venv should refuse a pre-existing target")
