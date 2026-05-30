"""Installer auto-patches INDEXED_SOURCE_DIRS for the host repo.

Without this, the deployed search_config.py defaults to ("tools/",
"schema/") - the less_tokens layout - and the host project's actual
source dirs are never indexed until the user edits the config by hand.

Same conservative posture as patch_venv_py: only patches when the
existing value is the source default; user customizations are
preserved.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
import install  # noqa: E402


def _write_default_config(p: Path) -> None:
    p.write_text(
        'INDEXED_SOURCE_DIRS: tuple[str, ...] = ("tools/", "schema/")\n'
        "OTHER = 1\n"
    )


def _host(tmp_path: Path, dirs_with_py: list[str]) -> Path:
    """Build a fake host repo with .py files under the named dirs."""
    for d in dirs_with_py:
        (tmp_path / d).mkdir(parents=True, exist_ok=True)
        (tmp_path / d / "mod.py").write_text("x = 1\n")
    return tmp_path


def test_discover_source_dirs_finds_top_level_py_dirs(tmp_path):
    _host(tmp_path, ["src", "lib", "app"])
    dirs = install._discover_source_dirs(tmp_path)
    assert set(dirs) == {"src/", "lib/", "app/"}


def test_discover_source_dirs_skips_venv_and_cache(tmp_path):
    _host(tmp_path, ["src", ".venv", "venv", "__pycache__", "node_modules"])
    dirs = install._discover_source_dirs(tmp_path)
    assert dirs == ["src/"]


def test_patch_replaces_default_with_discovered(tmp_path):
    cfg = tmp_path / "search_config.py"
    _write_default_config(cfg)
    _host(tmp_path, ["src", "lib"])
    patched = install.patch_indexed_source_dirs(cfg, tmp_path)
    assert patched == ("lib/", "src/")  # alpha-sorted
    text = cfg.read_text()
    assert 'INDEXED_SOURCE_DIRS: tuple[str, ...] = ("lib/", "src/",)' in text
    assert "OTHER = 1" in text  # surrounding content preserved


def test_patch_preserves_user_customization(tmp_path):
    cfg = tmp_path / "search_config.py"
    cfg.write_text(
        'INDEXED_SOURCE_DIRS: tuple[str, ...] = ("my_custom/",)\n'
    )
    _host(tmp_path, ["src"])
    patched = install.patch_indexed_source_dirs(cfg, tmp_path)
    assert patched is None
    assert "my_custom/" in cfg.read_text()


def test_patch_noop_when_no_python_dirs(tmp_path):
    cfg = tmp_path / "search_config.py"
    _write_default_config(cfg)
    # No .py files anywhere - nothing to suggest.
    patched = install.patch_indexed_source_dirs(cfg, tmp_path)
    assert patched is None
    assert "tools/" in cfg.read_text()  # default preserved
