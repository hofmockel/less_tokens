"""Regression: venv paths with a quote/backslash must not yield invalid Python.

install.py emits `VENV_PY = _venv_python("<path>")` in two places — the line
patch_venv_py writes into the host's search_config.py, and the next-steps hint
printed for the user to paste. Both interpolated the path raw, so a path with
an embedded `"` produced a SyntaxError: a broken config file, or an
un-pasteable hint. The fix routes both through `_venv_python_call()`, which
uses json.dumps to emit a valid Python string literal while keeping the
existing `"..."` form for ordinary paths.
"""
from __future__ import annotations

import ast
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO))
from install import (  # noqa: E402
    _venv_py_arg,
    _venv_py_assign,
    _venv_python_call,
    patch_venv_py,
)

SRC = REPO / "tools" / "search_config.py"


def _venv_py_value(text: str) -> str:
    """Parse `text` as Python; return the VENV_PY = _venv_python(<str>) arg."""
    assign = _venv_py_assign(ast.parse(text))
    assert assign is not None
    arg = _venv_py_arg(assign)
    assert arg is not None
    return arg


class TestVenvPythonCall:
    def test_plain_path_keeps_double_quotes(self):
        # Ordinary paths must stay byte-identical to the old form so the rest
        # of the install suite (which asserts the "..." shape) stays green.
        assert _venv_python_call(".venv") == '_venv_python(".venv")'

    @pytest.mark.parametrize(
        "path",
        [
            '/home/a"b/.venv',
            'C:\\Users\\quote"name\\.venv',
            "/tmp/back\\slash/.venv",
            "/plain/.venv-tokens/bin/python",
        ],
    )
    def test_emits_parseable_round_tripping_literal(self, path):
        line = f"VENV_PY = {_venv_python_call(path)}"
        assert _venv_py_value(line) == path


class TestPatchVenvPyWithQuote:
    def _setup_dst(self, tmp_path: Path) -> Path:
        dst = tmp_path / "tools" / "search_config.py"
        dst.parent.mkdir(parents=True)
        shutil.copy2(SRC, dst)
        return dst

    def test_written_config_is_valid_python_with_quoted_path(self, tmp_path):
        dst = self._setup_dst(tmp_path)
        # Venv outside target_root → _venv_config_str returns str(path); the
        # embedded quote then lands verbatim in the written config line.
        outside = tmp_path.parent / 'we"ird' / ".venv"
        result = patch_venv_py(dst, SRC, tmp_path, outside)
        assert result is not None
        assert '"' in result  # sanity: the path really did contain a quote
        # Pre-fix this raised SyntaxError; post-fix it parses and round-trips.
        assert _venv_py_value(dst.read_text()) == result
