"""End-to-end installation tests.

Each test installs into a tmp_path scratch directory, verifying a specific
install path (fresh / no-force / force / force+overwrite / config-merge / check).
tmp_path is passed as target_root directly into the helpers.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent.parent
SOURCE = REPO
sys.path.insert(0, str(REPO))
from install import (
    _diff_summary,
    copy_tree,
    handle_search_config,
    merge_search_config,
    patch_venv_py,
    wire_settings,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_fake_venv(root: Path) -> Path:
    """Create a minimal fake venv structure so detect_venv() finds it."""
    venv = root / ".venv"
    if sys.platform == "win32":
        py = venv / "Scripts" / "python.exe"
    else:
        py = venv / "bin" / "python"
    py.parent.mkdir(parents=True)
    py.write_text("#!/bin/sh\nexec python3 \"$@\"\n")
    if sys.platform != "win32":
        py.chmod(0o755)
    return venv


# ---------------------------------------------------------------------------
# copy_tree
# ---------------------------------------------------------------------------

class TestCopyTree:
    def test_fresh_install_copies_files(self, tmp_path):
        dst = tmp_path / "tools"
        copied = copy_tree(SOURCE / "tools", dst, tmp_path, force=False, overwrite_modified=False, label="tools")
        assert copied > 0
        assert (dst / "search_config.py").exists()
        assert (dst / "embeddings.py").exists()
        assert (dst / "search.py").exists()

    def test_no_force_skips_existing_files(self, tmp_path):
        dst = tmp_path / "tools"
        dst.mkdir()
        sentinel = dst / "search_config.py"
        sentinel.write_text("# my custom config\n")

        copy_tree(SOURCE / "tools", dst, tmp_path, force=False, overwrite_modified=False, label="tools")
        assert sentinel.read_text() == "# my custom config\n"

    def test_force_skips_identical_files(self, tmp_path):
        dst = tmp_path / "tools"
        dst.mkdir()
        src_config = SOURCE / "tools" / "search_config.py"
        dst_config = dst / "search_config.py"
        shutil.copy2(src_config, dst_config)

        copied = copy_tree(SOURCE / "tools", dst, tmp_path, force=True, overwrite_modified=False, label="tools")
        # Identical files don't count as copied
        assert dst_config.read_text() == src_config.read_text()

    def test_force_without_overwrite_modified_skips_changed(self, tmp_path):
        dst = tmp_path / "tools"
        dst.mkdir()
        custom = dst / "search_config.py"
        custom.write_text("# heavily customised\n")

        copy_tree(SOURCE / "tools", dst, tmp_path, force=True, overwrite_modified=False, label="tools")
        assert custom.read_text() == "# heavily customised\n"

    def test_force_plus_overwrite_modified_replaces_changed(self, tmp_path):
        dst = tmp_path / "tools"
        dst.mkdir()
        custom = dst / "db.py"
        custom.write_text("# old version\n")

        copy_tree(SOURCE / "tools", dst, tmp_path, force=True, overwrite_modified=True, label="tools",
                  exclude=frozenset({"search_config.py"}))
        assert custom.read_text() != "# old version\n"
        assert "old version" not in custom.read_text()

    def test_excludes_pyc_files(self, tmp_path):
        dst = tmp_path / "tools"
        copy_tree(SOURCE / "tools", dst, tmp_path, force=False, overwrite_modified=False, label="tools")
        pyc_files = list(dst.rglob("*.pyc"))
        assert pyc_files == []


# ---------------------------------------------------------------------------
# handle_search_config
# ---------------------------------------------------------------------------

class TestHandleSearchConfig:
    def test_copies_when_dst_missing(self, tmp_path):
        dst = tmp_path / "tools" / "search_config.py"
        handle_search_config(SOURCE / "tools" / "search_config.py", dst, tmp_path,
                             force_config=False, overwrite_modified=False)
        assert dst.exists()

    def test_merges_missing_variable(self, tmp_path):
        dst_dir = tmp_path / "tools"
        dst_dir.mkdir()
        dst = dst_dir / "search_config.py"
        dst.write_text("VENV_PY = None\n")

        handle_search_config(SOURCE / "tools" / "search_config.py", dst, tmp_path,
                             force_config=False, overwrite_modified=False)
        text = dst.read_text()
        assert "VENV_PY" in text
        # Should have gained new variables from source
        assert "INDEXED_SOURCE_DIRS" in text or "MAX_TOOL_OUTPUT_CHARS" in text

    def test_force_plus_overwrite_replaces_entirely(self, tmp_path):
        dst_dir = tmp_path / "tools"
        dst_dir.mkdir()
        dst = dst_dir / "search_config.py"
        dst.write_text("# old config\n")

        handle_search_config(SOURCE / "tools" / "search_config.py", dst, tmp_path,
                             force_config=True, overwrite_modified=True)
        assert "# old config" not in dst.read_text()
        assert "VENV_PY" in dst.read_text()


# ---------------------------------------------------------------------------
# patch_venv_py
# ---------------------------------------------------------------------------

class TestPatchVenvPy:
    SRC = SOURCE / "tools" / "search_config.py"

    def _setup_dst(self, tmp_path: Path) -> Path:
        """Drop a verbatim copy of the source config into tmp_path/tools/."""
        dst = tmp_path / "tools" / "search_config.py"
        dst.parent.mkdir(parents=True)
        shutil.copy2(self.SRC, dst)
        return dst

    def test_patches_default_value(self, tmp_path):
        dst = self._setup_dst(tmp_path)
        venv = tmp_path / ".venv"
        result = patch_venv_py(dst, self.SRC, tmp_path, venv)
        assert result == ".venv"
        assert 'VENV_PY = _venv_python(".venv")' in dst.read_text()

    def test_idempotent_when_already_correct(self, tmp_path):
        dst = self._setup_dst(tmp_path)
        venv = tmp_path / ".venv"
        first = patch_venv_py(dst, self.SRC, tmp_path, venv)
        assert first == ".venv"
        # Second run: value now differs from source default → no-op (returns None)
        second = patch_venv_py(dst, self.SRC, tmp_path, venv)
        assert second is None

    def test_preserves_user_customization(self, tmp_path):
        dst = self._setup_dst(tmp_path)
        # User edits VENV_PY to a custom path
        text = dst.read_text().replace(
            'VENV_PY = _venv_python("app/.venv")',
            'VENV_PY = _venv_python(".my-venv")',
        )
        dst.write_text(text)
        venv = tmp_path / ".venv"
        result = patch_venv_py(dst, self.SRC, tmp_path, venv)
        assert result is None
        assert 'VENV_PY = _venv_python(".my-venv")' in dst.read_text()

    def test_returns_none_when_venv_py_missing(self, tmp_path):
        dst = tmp_path / "tools" / "search_config.py"
        dst.parent.mkdir(parents=True)
        dst.write_text("# config without VENV_PY\n")
        result = patch_venv_py(dst, self.SRC, tmp_path, tmp_path / ".venv")
        assert result is None

    def test_falls_back_to_absolute_when_outside_target(self, tmp_path):
        dst = self._setup_dst(tmp_path)
        # Venv lives outside target_root → relative_to fails, expect absolute path
        outside = tmp_path.parent / "external_venv"
        result = patch_venv_py(dst, self.SRC, tmp_path, outside)
        assert result == str(outside).replace("\\", "/")
        assert f'_venv_python("{result}")' in dst.read_text()

    def test_preserves_surrounding_lines(self, tmp_path):
        dst = self._setup_dst(tmp_path)
        before = dst.read_text()
        # The line right before VENV_PY is a comment explaining the variable;
        # the line right after is a blank, then EXCLUDED_DIR_NAMES.
        venv = tmp_path / ".venv"
        patch_venv_py(dst, self.SRC, tmp_path, venv)
        after = dst.read_text()
        # Same number of lines (single-line assignment replaced with single line)
        assert before.count("\n") == after.count("\n")
        # Comment preserved
        assert "# Venv python used for embeddings" in after
        # Next variable still parses
        assert "EXCLUDED_DIR_NAMES" in after


# ---------------------------------------------------------------------------
# wire_settings (integration: full round-trip including file I/O)
# ---------------------------------------------------------------------------

class TestWireSettingsIntegration:
    def test_fresh_install_wires_core_hooks(self, tmp_path):
        settings = tmp_path / ".claude" / "settings.local.json"
        venv_py = tmp_path / ".venv" / "bin" / "python"
        py = str(venv_py)
        entries = [
            ("PreToolUse", "Read", f"{py} .claude/hooks/search-first.py"),
            ("PostToolUse", "Edit|Write", f"{py} .claude/hooks/index-refresh.py"),
        ]
        added, present = wire_settings(settings, entries)
        assert added == 2
        assert present == 0
        data = json.loads(settings.read_text())
        assert len(data["hooks"]["PreToolUse"]) == 1
        assert len(data["hooks"]["PostToolUse"]) == 1

    def test_second_install_reports_all_present(self, tmp_path):
        settings = tmp_path / ".claude" / "settings.local.json"
        entries = [("PreToolUse", "Read", "python hook.py")]
        wire_settings(settings, entries)
        added, present = wire_settings(settings, entries)
        assert added == 0
        assert present == 1

    def test_optional_hooks_added_separately(self, tmp_path):
        settings = tmp_path / ".claude" / "settings.local.json"
        core = [("PreToolUse", "Read", "python sf.py")]
        optional = [("PostToolUse", "Bash|Read|WebFetch", "python trunc.py")]
        wire_settings(settings, core)
        added, _ = wire_settings(settings, optional)
        assert added == 1
        data = json.loads(settings.read_text())
        assert len(data["hooks"]["PostToolUse"]) == 1


# ---------------------------------------------------------------------------
# _diff_summary
# ---------------------------------------------------------------------------

class TestDiffSummary:
    def test_added_lines(self):
        summary = _diff_summary("a\nb\nc\n", "a\nb\n")
        assert "+1" in summary

    def test_removed_lines(self):
        summary = _diff_summary("a\nb\n", "a\nb\nc\n")
        assert "-1" in summary

    def test_identical_is_zero_zero(self):
        summary = _diff_summary("a\nb\n", "a\nb\n")
        assert "+0" in summary
        assert "-0" in summary
