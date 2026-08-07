"""Regression test: _extract_block must include all lines of multi-line assignments."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(REPO))
from install import _extract_block, merge_search_config


def test_single_line_assignment():
    lines = ["X = 1"]
    assert _extract_block(lines, lineno=1, end_lineno=1) == "X = 1"


def test_multiline_set():
    lines = [
        "EXCLUDED = {",
        '    "foo",',
        '    "bar",',
        "}",
    ]
    result = _extract_block(lines, lineno=1, end_lineno=4)
    assert result == 'EXCLUDED = {\n    "foo",\n    "bar",\n}'


def test_multiline_dict():
    lines = [
        "CONFIG = {",
        '    "a": 1,',
        '    "b": 2,',
        "}",
    ]
    result = _extract_block(lines, lineno=1, end_lineno=4)
    assert result == 'CONFIG = {\n    "a": 1,\n    "b": 2,\n}'


def test_multiline_with_preceding_comment():
    lines = [
        "# Maximum chunk size",
        "MAX_CHUNK = {",
        '    "default": 512,',
        "}",
    ]
    result = _extract_block(lines, lineno=2, end_lineno=4)
    assert result == '# Maximum chunk size\nMAX_CHUNK = {\n    "default": 512,\n}'


def test_merge_injects_full_multiline_assignment(tmp_path):
    """merge_search_config must inject the full multi-line block, not just the first line."""
    src = tmp_path / "src.py"
    dst = tmp_path / "dst.py"
    src.write_text(
        'EXCLUDED = {\n    "foo",\n    "bar",\n}\n',
        encoding="utf-8",
    )
    dst.write_text("X = 1\n", encoding="utf-8")

    added = merge_search_config(src, dst)
    assert added == ["EXCLUDED"]
    content = dst.read_text(encoding="utf-8")
    assert '"foo"' in content
    assert '"bar"' in content
    assert content.count("}") >= 1
