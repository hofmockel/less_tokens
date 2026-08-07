"""CX25: Bash-command read detection for Codex's mcp__filesystem__-only hooks.

Unit-level coverage of `_parse_bash_read`/`map_bash_read` in
`agents/codex/hooks/_codex_runtime.py` — the mapper that lets `cat`, `head`,
`tail`, and `sed -n` reads reach the 6 hooks that otherwise only fire on the
opt-in `mcp__filesystem__` matcher. See `.claude/tests/unit/test_codex_hooks.py`
for the end-to-end subprocess wiring proof.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(
    0, str(Path(__file__).parent.parent.parent.parent / "agents" / "codex" / "hooks")
)

from _codex_runtime import _parse_bash_read, map_bash_read  # noqa: E402


class TestParseBashRead:
    @pytest.mark.parametrize(
        "command,expected_path,expected_offset",
        [
            ("cat src/app.py", "src/app.py", None),
            ("cat /repo/README.md", "/repo/README.md", None),
            ("head -n 20 src/app.py", "src/app.py", 1),
            ("head -20 src/app.py", "src/app.py", 1),
            ("head src/app.py", "src/app.py", 1),
            ("tail -n 20 src/app.py", "src/app.py", 1),
            ("sed -n '5,9p' src/app.py", "src/app.py", 5),
            ("sed -n '12p' src/app.py", "src/app.py", 12),
            (
                r"cat C:\Users\runneradmin\AppData\Local\Temp\app.py",
                r"C:\Users\runneradmin\AppData\Local\Temp\app.py",
                None,
            ),
        ],
    )
    def test_recognizes_single_file_read_shapes(
        self, command, expected_path, expected_offset
    ):
        assert _parse_bash_read(command) == (expected_path, expected_offset)

    def test_windows_path_backslashes_survive_shlex_posix_mode(self):
        """POSIX-mode shlex.split() treats backslash as an escape char and used to strip it, mangling Windows paths."""
        command = r"cat C:\Users\runneradmin\AppData\Local\Temp\pytest-0\app.py"
        result = _parse_bash_read(command)
        assert result is not None
        path, offset = result
        assert path == r"C:\Users\runneradmin\AppData\Local\Temp\pytest-0\app.py"
        assert offset is None

    @pytest.mark.parametrize(
        "command",
        [
            "cat a.txt b.txt",  # multiple files
            "cat -n a.txt",  # unsupported flag
            "cat a.txt | head",  # pipe
            "cat a.txt > out.txt",  # redirect
            "cat $(git diff --name-only)",  # substitution
            "cat `git diff --name-only`",  # backtick substitution
            "cat a.txt; rm a.txt",  # chaining
            "cat a.txt && echo done",  # chaining
            "tail -f app.log",  # follow — not a bounded read
            "head -c 100 a.txt",  # byte mode, not line-bounded
            "sed '5,9p' a.txt",  # missing -n: prints whole file too
            "sed -n '5,9p' a.txt b.txt",  # multiple files
            "grep foo a.txt",  # not a whitelisted command
            "cat *.py",  # glob
            "",
            "   ",
        ],
    )
    def test_leaves_ambiguous_or_unsupported_shapes_unmapped(self, command):
        assert _parse_bash_read(command) is None

    def test_unbalanced_quotes_fail_open(self):
        assert _parse_bash_read("cat 'unterminated") is None


class TestMapBashRead:
    def test_rewrites_bash_cat_to_synthetic_read(self):
        raw = {"tool_name": "Bash", "tool_input": {"command": "cat src/app.py"}}
        mapped = map_bash_read(raw)
        assert mapped["tool_name"] == "Read"
        assert mapped["tool_input"] == {"file_path": "src/app.py"}

    def test_rewrites_bash_sed_to_synthetic_read_with_offset(self):
        raw = {
            "tool_name": "Bash",
            "tool_input": {"command": "sed -n '5,9p' src/app.py"},
        }
        mapped = map_bash_read(raw)
        assert mapped["tool_name"] == "Read"
        assert mapped["tool_input"] == {"file_path": "src/app.py", "offset": 5}

    def test_leaves_non_read_bash_untouched(self):
        raw = {"tool_name": "Bash", "tool_input": {"command": "pytest -q"}}
        assert map_bash_read(dict(raw)) == raw

    def test_leaves_non_bash_tools_untouched(self):
        raw = {
            "tool_name": "mcp__filesystem__read_text_file",
            "tool_input": {"path": "a.py"},
        }
        assert map_bash_read(dict(raw)) == raw

    def test_missing_command_fails_open(self):
        raw = {"tool_name": "Bash", "tool_input": {}}
        assert map_bash_read(dict(raw)) == raw
