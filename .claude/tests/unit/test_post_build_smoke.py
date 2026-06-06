"""build_index runs a smoke assertion after a successful refresh.

Catches a broken or empty index at install time instead of letting the
user discover it on first search. Implementation: an extra subprocess
call to `embeddings.py stats` (or `health`) after refresh succeeds, so
the install output ends with a one-line confidence message.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import install  # noqa: E402


def test_build_index_smoke_checks_after_refresh(tmp_path, monkeypatch):
    calls: list[list[str]] = []

    def fake_check_call(cmd, cwd=None, **kw):
        calls.append([str(c) for c in cmd])
        return 0

    monkeypatch.setattr(subprocess, "check_call", fake_check_call)
    rc = install.build_index(Path("/venv/py"), tmp_path)
    assert rc == 0
    # First call is the refresh, second is the smoke check.
    assert len(calls) >= 2, f"expected smoke-check subprocess after refresh, got {calls}"
    refresh, smoke = calls[0], calls[1]
    assert refresh[1].endswith("embeddings.py") and refresh[2] == "refresh"
    assert smoke[1].endswith("embeddings.py")
    assert smoke[2] in {"stats", "health"}


def test_build_index_dry_run_skips_smoke(tmp_path, monkeypatch):
    calls: list[list[str]] = []
    monkeypatch.setattr(subprocess, "check_call", lambda c, **k: calls.append(c) or 0)
    rc = install.build_index(Path("/venv/py"), tmp_path, dry_run=True)
    assert rc == 0
    assert calls == []  # dry-run writes nothing, runs nothing


def test_build_index_skips_smoke_when_refresh_fails(tmp_path, monkeypatch):
    def fail_first(cmd, cwd=None, **kw):
        raise subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr(subprocess, "check_call", fail_first)
    rc = install.build_index(Path("/venv/py"), tmp_path)
    assert rc == 1
