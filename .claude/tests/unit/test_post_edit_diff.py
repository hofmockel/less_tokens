"""Unit tests for post-edit-diff.py and read-after-edit.py hooks."""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from tests.conftest import load_hook

HOOKS_DIR = Path(__file__).resolve().parent.parent.parent / "hooks"
PED = HOOKS_DIR / "post-edit-diff.py"
RAE = HOOKS_DIR / "read-after-edit.py"


@pytest.fixture(scope="module")
def ped():
    return load_hook(PED)


@pytest.fixture(scope="module")
def rae():
    return load_hook(RAE)


# ---------------------------------------------------------------------------
# post-edit-diff: _diff_edit
# ---------------------------------------------------------------------------

class TestDiffEdit:
    def test_basic_change(self, ped):
        lines = ped._diff_edit("foo = 1\n", "foo = 2\n", "x.py")
        joined = "".join(lines)
        assert "-foo = 1" in joined
        assert "+foo = 2" in joined

    def test_empty_old_empty_new(self, ped):
        lines = ped._diff_edit("", "", "x.py")
        assert lines == []

    def test_multiline(self, ped):
        old = "a\nb\nc\n"
        new = "a\nB\nc\n"
        lines = ped._diff_edit(old, new, "f.py")
        joined = "".join(lines)
        assert "-b" in joined
        assert "+B" in joined

    def test_labels_in_header(self, ped):
        lines = ped._diff_edit("x\n", "y\n", "myfile.py")
        header = "".join(lines[:2])
        assert "a/myfile.py" in header
        assert "b/myfile.py" in header


# ---------------------------------------------------------------------------
# post-edit-diff: _cap
# ---------------------------------------------------------------------------

class TestCap:
    def test_no_cap_when_zero(self, ped):
        lines = ["line\n"] * 200
        result = ped._cap(lines, 0)
        assert result.count("line\n") == 200

    def test_truncates_at_max(self, ped):
        lines = [f"line{i}\n" for i in range(100)]
        result = ped._cap(lines, 10)
        assert "line9" in result
        assert "line10" not in result
        assert "+90 more diff lines" in result

    def test_no_truncation_when_under(self, ped):
        lines = ["a\n", "b\n"]
        result = ped._cap(lines, 60)
        assert result == "a\nb\n"


# ---------------------------------------------------------------------------
# post-edit-diff: _record_edit + main
# ---------------------------------------------------------------------------

class TestRecordEdit:
    def test_record_writes_path(self, ped, tmp_path, monkeypatch):
        monkeypatch.setattr(ped, "_active_state_dir", lambda: tmp_path)
        ped._record_edit("/some/file.py")
        data = json.loads((tmp_path / "last-edit.json").read_text())
        assert "/some/file.py" in data
        assert isinstance(data["/some/file.py"], float)

    def test_record_accumulates_multiple_files(self, ped, tmp_path, monkeypatch):
        monkeypatch.setattr(ped, "_active_state_dir", lambda: tmp_path)
        ped._record_edit("/a.py")
        ped._record_edit("/b.py")
        data = json.loads((tmp_path / "last-edit.json").read_text())
        assert "/a.py" in data
        assert "/b.py" in data


class TestPedMain:
    def _run(self, ped, payload: dict, capsys) -> int:
        import io
        import sys as _sys
        old_stdin = _sys.stdin
        _sys.stdin = io.StringIO(json.dumps(payload))
        try:
            rc = ped.main()
        finally:
            _sys.stdin = old_stdin
        return rc

    def test_edit_emits_diff(self, ped, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(ped, "_active_state_dir", lambda: tmp_path)
        payload = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "/tmp/foo.py",
                "old_string": "x = 1\n",
                "new_string": "x = 2\n",
            },
        }
        rc = self._run(ped, payload, capsys)
        assert rc == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        ctx = data["hookSpecificOutput"]["additionalContext"]
        assert "-x = 1" in ctx
        assert "+x = 2" in ctx

    def test_non_edit_write_noop(self, ped, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(ped, "_active_state_dir", lambda: tmp_path)
        payload = {"tool_name": "Read", "tool_input": {"file_path": "/tmp/x.py"}}
        rc = self._run(ped, payload, capsys)
        assert rc == 0
        assert capsys.readouterr().out.strip() == ""

    def test_edit_empty_strings_noop(self, ped, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(ped, "_active_state_dir", lambda: tmp_path)
        payload = {
            "tool_name": "Edit",
            "tool_input": {"file_path": "/tmp/f.py", "old_string": "", "new_string": ""},
        }
        rc = self._run(ped, payload, capsys)
        assert rc == 0
        assert capsys.readouterr().out.strip() == ""


# ---------------------------------------------------------------------------
# read-after-edit: main
# ---------------------------------------------------------------------------

class TestRaeMain:
    def _run(self, rae, payload: dict) -> tuple[int, str]:
        import io
        import sys as _sys
        old_stdin, old_stderr = _sys.stdin, _sys.stderr
        _sys.stdin = io.StringIO(json.dumps(payload))
        err_buf = io.StringIO()
        _sys.stderr = err_buf
        try:
            rc = rae.main()
        finally:
            _sys.stdin = old_stdin
            _sys.stderr = old_stderr
        return rc, err_buf.getvalue()

    def _write_edits(self, rae, tmp_path, monkeypatch, entries: dict):
        last_edit = tmp_path / "last-edit.json"
        last_edit.write_text(json.dumps(entries))
        monkeypatch.setattr(rae, "_active_state_dir", lambda: tmp_path)
        monkeypatch.setattr(rae, "LAST_EDIT_WINDOW_SECONDS", 120)

    def test_recent_edit_blocks(self, rae, tmp_path, monkeypatch):
        real_file = tmp_path / "foo.py"
        real_file.touch()
        abs_path = str(real_file.resolve())
        self._write_edits(rae, tmp_path, monkeypatch, {abs_path: time.time()})
        rc, err = self._run(rae, {
            "tool_name": "Read",
            "tool_input": {"file_path": str(real_file)},
        })
        assert rc == 2
        assert "diff already in context" in err

    def test_old_edit_allows(self, rae, tmp_path, monkeypatch):
        old_ts = time.time() - 300  # 5 min ago
        self._write_edits(rae, tmp_path, monkeypatch, {"/abs/foo.py": old_ts})
        import unittest.mock as mock
        with mock.patch("pathlib.Path.resolve", return_value=Path("/abs/foo.py")):
            rc, _ = self._run(rae, {
                "tool_name": "Read",
                "tool_input": {"file_path": "foo.py"},
            })
        assert rc == 0

    def test_offset_always_allows(self, rae, tmp_path, monkeypatch):
        self._write_edits(rae, tmp_path, monkeypatch, {"/abs/foo.py": time.time()})
        import unittest.mock as mock
        with mock.patch("pathlib.Path.resolve", return_value=Path("/abs/foo.py")):
            rc, _ = self._run(rae, {
                "tool_name": "Read",
                "tool_input": {"file_path": "foo.py", "offset": 10},
            })
        assert rc == 0

    def test_different_file_allows(self, rae, tmp_path, monkeypatch):
        self._write_edits(rae, tmp_path, monkeypatch, {"/abs/bar.py": time.time()})
        import unittest.mock as mock
        with mock.patch("pathlib.Path.resolve", return_value=Path("/abs/foo.py")):
            rc, _ = self._run(rae, {
                "tool_name": "Read",
                "tool_input": {"file_path": "foo.py"},
            })
        assert rc == 0

    def test_no_state_file_allows(self, rae, tmp_path, monkeypatch):
        monkeypatch.setattr(rae, "_active_state_dir", lambda: tmp_path / "no_state")
        rc, _ = self._run(rae, {
            "tool_name": "Read",
            "tool_input": {"file_path": "anything.py"},
        })
        assert rc == 0

    def test_non_read_tool_noop(self, rae, tmp_path, monkeypatch):
        self._write_edits(rae, tmp_path, monkeypatch, {"/abs/foo.py": time.time()})
        rc, _ = self._run(rae, {"tool_name": "Bash", "tool_input": {"command": "ls"}})
        assert rc == 0


# ---------------------------------------------------------------------------
# post-edit-diff: _diff_write uses file's repo, not less_tokens REPO
# ---------------------------------------------------------------------------

class TestDiffWriteHostRepo:
    """Regression: _diff_write must run git diff in the file's own repo."""

    def test_diff_uses_files_repo(self, ped, tmp_path):
        """_diff_write should show a proper diff against the file's git history,
        not treat the file as untracked because git ran in the wrong repo."""
        import subprocess

        # Set up a temp git repo with one committed file
        subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            check=True, capture_output=True, cwd=tmp_path,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            check=True, capture_output=True, cwd=tmp_path,
        )
        target = tmp_path / "target.py"
        target.write_text("original = 1\n")
        subprocess.run(["git", "add", "target.py"], check=True, capture_output=True, cwd=tmp_path)
        subprocess.run(
            ["git", "commit", "-m", "init"],
            check=True, capture_output=True, cwd=tmp_path,
        )

        # Modify without committing (working-tree change)
        target.write_text("modified = 2\n")

        diff_lines = ped._diff_write(str(target))
        diff_text = "".join(diff_lines)

        # Must show removal of original line, not just all-new (untracked) output
        assert "-original = 1" in diff_text, (
            f"Expected proper diff against committed version; got:\n{diff_text}"
        )
