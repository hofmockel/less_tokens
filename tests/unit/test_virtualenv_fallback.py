"""$VIRTUAL_ENV is the first signal for venv detection.

`activate` exports VIRTUAL_ENV pointing at the live venv on every
platform. Both install.detect_venv() and search_config (VENV_PY) now
prefer it over relative-path guesses, so an activated venv is used
without editing search_config or passing --venv.
"""
from __future__ import annotations

import sys
from pathlib import Path

from tests.conftest import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools"))
import install  # noqa: E402
import search_config  # noqa: E402


def _make_venv(root: Path) -> Path:
    """Create a venv-shaped dir with a python interpreter file."""
    if sys.platform == "win32":
        py = root / "Scripts" / "python.exe"
    else:
        py = root / "bin" / "python"
    py.parent.mkdir(parents=True, exist_ok=True)
    py.write_text("")
    return root


def test_detect_venv_prefers_virtual_env(tmp_path, monkeypatch):
    active = _make_venv(tmp_path / "myenv")
    target = tmp_path / "proj"
    target.mkdir()
    # A different candidate under target_root exists too...
    _make_venv(target / ".venv")
    monkeypatch.setenv("VIRTUAL_ENV", str(active))

    assert install.detect_venv(target) == active


def test_detect_venv_ignores_missing_virtual_env(tmp_path, monkeypatch):
    target = tmp_path / "proj"
    _make_venv(target / ".venv")
    monkeypatch.setenv("VIRTUAL_ENV", str(tmp_path / "gone"))

    assert install.detect_venv(target) == target / ".venv"


def test_detect_venv_unset_env_uses_candidates(tmp_path, monkeypatch):
    target = tmp_path / "proj"
    _make_venv(target / ".venv")
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)

    assert install.detect_venv(target) == target / ".venv"


def test_active_venv_python_resolves_from_env(tmp_path, monkeypatch):
    active = _make_venv(tmp_path / "venvX")
    monkeypatch.setenv("VIRTUAL_ENV", str(active))

    py = search_config._active_venv_python()
    assert py is not None
    assert py.parent.parent == active
    assert py.exists()


def test_active_venv_python_none_when_unset_or_missing(tmp_path, monkeypatch):
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
    assert search_config._active_venv_python() is None

    monkeypatch.setenv("VIRTUAL_ENV", str(tmp_path / "nope"))
    assert search_config._active_venv_python() is None
