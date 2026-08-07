"""Unit tests for merge_search_config and handle_search_config in install.py."""

from __future__ import annotations

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from install import _top_level_assignments, merge_search_config


class TestTopLevelAssignments:
    def test_simple_assign(self, tmp_path):
        f = tmp_path / "c.py"
        f.write_text("FOO = 1\nBAR = 2\n")
        result = _top_level_assignments(f.read_text())
        assert "FOO" in result
        assert "BAR" in result

    def test_annotated_assign(self, tmp_path):
        f = tmp_path / "c.py"
        f.write_text("X: int = 42\n")
        result = _top_level_assignments(f.read_text())
        assert "X" in result

    def test_syntax_error_returns_empty(self):
        result = _top_level_assignments("def foo(:\n    pass\n")
        assert result == {}

    def test_function_not_included(self):
        result = _top_level_assignments("def foo(): pass\nBAR = 1\n")
        assert "foo" not in result
        assert "BAR" in result


class TestMergeSearchConfig:
    def test_adds_missing_variable(self, tmp_path):
        src = tmp_path / "src.py"
        dst = tmp_path / "dst.py"
        src.write_text("NEW_VAR = 99\nEXISTING = 'hello'\n")
        dst.write_text("EXISTING = 'hello'\n")

        added = merge_search_config(src, dst)

        assert "NEW_VAR" in added
        assert "EXISTING" not in added
        dst_text = dst.read_text()
        assert "NEW_VAR = 99" in dst_text

    def test_does_not_duplicate_existing_variable(self, tmp_path):
        src = tmp_path / "src.py"
        dst = tmp_path / "dst.py"
        src.write_text("EXISTING = 'hello'\n")
        dst.write_text("EXISTING = 'world'\n")

        added = merge_search_config(src, dst)

        assert added == []
        assert dst.read_text().count("EXISTING") == 1

    def test_preserves_preceding_comment(self, tmp_path):
        src = tmp_path / "src.py"
        dst = tmp_path / "dst.py"
        src.write_text("# The new variable\nNEW_VAR = 99\nOLD = 1\n")
        dst.write_text("OLD = 1\n")

        merge_search_config(src, dst)

        dst_text = dst.read_text()
        assert "# The new variable" in dst_text
        assert "NEW_VAR = 99" in dst_text

    def test_returns_empty_when_all_present(self, tmp_path):
        src = tmp_path / "src.py"
        dst = tmp_path / "dst.py"
        src.write_text("A = 1\nB = 2\n")
        dst.write_text("A = 1\nB = 2\n")

        added = merge_search_config(src, dst)
        assert added == []

    def test_multiple_missing_variables(self, tmp_path):
        src = tmp_path / "src.py"
        dst = tmp_path / "dst.py"
        src.write_text("A = 1\nB = 2\nC = 3\n")
        dst.write_text("A = 1\n")

        added = merge_search_config(src, dst)
        assert "B" in added
        assert "C" in added
        dst_text = dst.read_text()
        assert "B = 2" in dst_text
        assert "C = 3" in dst_text

    def test_appended_block_marker(self, tmp_path):
        src = tmp_path / "src.py"
        dst = tmp_path / "dst.py"
        src.write_text("NEW = 1\n")
        dst.write_text("")

        merge_search_config(src, dst)
        assert "# --- Added by less_tokens installer ---" in dst.read_text()
