"""Tests for agents/common/hooks/ — HookPayload, normalizers, and gate functions."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / ".claude" / "tools"))

from agents.common.hooks.payload import HookPayload, normalize_claude, normalize_codex
from agents.common.hooks.search_first import is_indexed, search_was_recent
from agents.common.hooks.truncate_output import check_truncate_output
from agents.common.hooks.compact_trigger import check_compact_trigger


# ---------------------------------------------------------------------------
# normalize_claude
# ---------------------------------------------------------------------------

class TestNormalizeClaude:
    def test_reads_tool_result(self):
        p = normalize_claude({"tool_name": "Bash", "tool_input": {}, "tool_result": "out"})
        assert p.agent == "claude"
        assert p.tool_output == "out"

    def test_falls_back_to_tool_response(self):
        p = normalize_claude({"tool_name": "Read", "tool_input": {}, "tool_response": "content"})
        assert p.tool_output == "content"

    def test_tool_result_preferred_over_tool_response(self):
        p = normalize_claude({"tool_name": "Bash", "tool_input": {},
                               "tool_result": "result", "tool_response": "response"})
        assert p.tool_output == "result"

    def test_extracts_touched_files(self):
        p = normalize_claude({"tool_name": "Edit",
                               "tool_input": {"file_path": "/a/b.py"}, "tool_result": ""})
        assert p.touched_files == (Path("/a/b.py"),)

    def test_no_touched_files_without_file_path(self):
        p = normalize_claude({"tool_name": "Bash", "tool_input": {}, "tool_result": ""})
        assert p.touched_files == ()

    def test_transcript_path_parsed(self):
        p = normalize_claude({"tool_name": "Bash", "tool_input": {}, "tool_result": "",
                               "transcript_path": "/tmp/t.json"})
        assert p.transcript_path == Path("/tmp/t.json")

    def test_none_transcript_path(self):
        p = normalize_claude({"tool_name": "Bash", "tool_input": {}, "tool_result": ""})
        assert p.transcript_path is None

    def test_non_string_output_serialized(self):
        p = normalize_claude({"tool_name": "Bash", "tool_input": {},
                               "tool_result": {"key": "val"}})
        assert '"key"' in p.tool_output


# ---------------------------------------------------------------------------
# normalize_codex
# ---------------------------------------------------------------------------

class TestNormalizeCodex:
    def test_reads_tool_response_first(self):
        p = normalize_codex({"tool_name": "Bash", "tool_input": {},
                              "tool_response": "resp", "tool_result": "res"})
        assert p.tool_output == "resp"

    def test_falls_back_to_tool_result(self):
        p = normalize_codex({"tool_name": "Bash", "tool_input": {}, "tool_result": "result"})
        assert p.tool_output == "result"

    def test_apply_patch_has_empty_touched_files(self):
        p = normalize_codex({"tool_name": "apply_patch",
                              "tool_input": {"file_path": "/a/b.py"}, "tool_response": ""})
        assert p.touched_files == ()

    def test_edit_extracts_touched_files(self):
        p = normalize_codex({"tool_name": "Edit",
                              "tool_input": {"file_path": "/a/b.py"}, "tool_response": ""})
        assert p.touched_files == (Path("/a/b.py"),)

    def test_agent_field_is_codex(self):
        p = normalize_codex({"tool_name": "Bash", "tool_input": {}, "tool_response": ""})
        assert p.agent == "codex"

    def test_non_string_output_serialized(self):
        p = normalize_codex({"tool_name": "Bash", "tool_input": {},
                              "tool_response": {"key": "val"}})
        assert '"key"' in p.tool_output


# ---------------------------------------------------------------------------
# is_indexed
# ---------------------------------------------------------------------------

class TestIsIndexed:
    def test_root_md_is_indexed(self, tmp_path):
        (tmp_path / "README.md").touch()
        assert is_indexed(tmp_path / "README.md", tmp_path)

    def test_root_py_is_indexed(self, tmp_path):
        (tmp_path / "install.py").touch()
        assert is_indexed(tmp_path / "install.py", tmp_path)

    def test_root_sql_is_indexed(self, tmp_path):
        (tmp_path / "schema.sql").touch()
        assert is_indexed(tmp_path / "schema.sql", tmp_path)

    def test_outside_repo_returns_false(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        outside = tmp_path / "outside.md"
        outside.touch()
        assert not is_indexed(outside, repo)

    def test_excluded_dir_name_returns_false(self, tmp_path):
        excluded = tmp_path / ".venv" / "site.md"
        excluded.parent.mkdir()
        excluded.touch()
        assert not is_indexed(excluded, tmp_path, excluded_names={".venv"})

    def test_excluded_prefix_returns_false(self, tmp_path):
        nested = tmp_path / "app" / ".venv" / "file.py"
        nested.parent.mkdir(parents=True)
        nested.touch()
        assert not is_indexed(nested, tmp_path, excluded_prefixes=("app/.venv/",))

    def test_indexed_dir_py_is_indexed(self, tmp_path):
        src = tmp_path / "src" / "module.py"
        src.parent.mkdir()
        src.touch()
        assert is_indexed(src, tmp_path, indexed_dirs=("src/",))

    def test_subdir_py_not_indexed_without_indexed_dirs(self, tmp_path):
        src = tmp_path / "src" / "module.py"
        src.parent.mkdir()
        src.touch()
        assert not is_indexed(src, tmp_path)

    def test_txt_file_not_indexed(self, tmp_path):
        f = tmp_path / "notes.txt"
        f.touch()
        assert not is_indexed(f, tmp_path)


# ---------------------------------------------------------------------------
# search_was_recent
# ---------------------------------------------------------------------------

class TestSearchWasRecent:
    def test_returns_false_when_no_file(self, tmp_path):
        assert not search_was_recent(tmp_path, 300)

    def test_returns_true_when_recent(self, tmp_path):
        (tmp_path / "last-search").touch()
        assert search_was_recent(tmp_path, 300)

    def test_returns_false_when_stale(self, tmp_path):
        f = tmp_path / "last-search"
        f.touch()
        old = time.time() - 400
        os.utime(f, (old, old))
        assert not search_was_recent(tmp_path, 300)


# ---------------------------------------------------------------------------
# check_truncate_output
# ---------------------------------------------------------------------------

def _payload(tool: str, output: str) -> HookPayload:
    return HookPayload(agent="claude", tool_name=tool, tool_input={},
                       tool_output=output, transcript_path=None, touched_files=())


class TestCheckTruncateOutput:
    def test_passes_small_bash(self):
        code, _, _ = check_truncate_output(
            _payload("Bash", "x" * 100),
            max_chars=4000, head_lines=50, tail_lines=20, max_glob_results=100)
        assert code == 0

    def test_truncates_large_bash(self):
        code, stdout, _ = check_truncate_output(
            _payload("Bash", "x" * 10_000),
            max_chars=4000, head_lines=50, tail_lines=20, max_glob_results=100)
        assert code == 2
        assert "omitted" in stdout

    def test_passes_unrelated_tool(self):
        code, _, _ = check_truncate_output(
            _payload("Edit", "x" * 10_000),
            max_chars=4000, head_lines=50, tail_lines=20, max_glob_results=100)
        assert code == 0

    def test_disabled_when_max_chars_zero(self):
        code, _, _ = check_truncate_output(
            _payload("Bash", "x" * 10_000),
            max_chars=0, head_lines=50, tail_lines=20, max_glob_results=100)
        assert code == 0

    def test_glob_line_cap(self):
        lines = "\n".join(f"file{i}.py" for i in range(200))
        code, stdout, _ = check_truncate_output(
            _payload("Glob", lines),
            max_chars=0, head_lines=50, tail_lines=20, max_glob_results=10)
        assert code == 2
        assert "more file" in stdout

    def test_read_truncated_by_char_ceiling(self):
        code, stdout, _ = check_truncate_output(
            _payload("Read", "x" * 10_000),
            max_chars=4000, head_lines=50, tail_lines=20, max_glob_results=100)
        assert code == 2
        assert len(stdout) <= 5000


# ---------------------------------------------------------------------------
# check_compact_trigger
# ---------------------------------------------------------------------------

def _compact_payload(transcript_path=None) -> HookPayload:
    return HookPayload(agent="claude", tool_name="Bash", tool_input={},
                       tool_output="", transcript_path=transcript_path, touched_files=())


class TestCheckCompactTrigger:
    def test_passes_when_disabled(self, tmp_path):
        code, _, _ = check_compact_trigger(
            _compact_payload(), state_dir=tmp_path,
            max_session_chars=0, message="msg")
        assert code == 0

    def test_passes_when_no_transcript(self, tmp_path):
        code, _, _ = check_compact_trigger(
            _compact_payload(), state_dir=tmp_path,
            max_session_chars=100, message="msg")
        assert code == 0

    def test_fires_when_transcript_exceeds_threshold(self, tmp_path):
        transcript = tmp_path / "session.json"
        transcript.write_text("x" * 1000)
        code, _, stderr = check_compact_trigger(
            _compact_payload(transcript), state_dir=tmp_path,
            max_session_chars=100, message="Session is {size:,} chars.")
        assert code == 2
        assert "1,000" in stderr

    def test_writes_state_file_on_fire(self, tmp_path):
        transcript = tmp_path / "session.json"
        transcript.write_text("x" * 1000)
        check_compact_trigger(
            _compact_payload(transcript), state_dir=tmp_path,
            max_session_chars=100, message="msg")
        assert (tmp_path / "compact-trigger-last").exists()

    def test_hysteresis_suppresses_repeat_fire(self, tmp_path):
        transcript = tmp_path / "session.json"
        transcript.write_text("x" * 1000)
        (tmp_path / "compact-trigger-last").write_text("999")
        code, _, _ = check_compact_trigger(
            _compact_payload(transcript), state_dir=tmp_path,
            max_session_chars=100, message="msg")
        assert code == 0
