"""Tests for agents/common/hooks/ — HookPayload, normalizers, and gate functions."""

from __future__ import annotations

import os
import json
import sys
import time
from pathlib import Path


REPO = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / ".claude" / "tools"))

from agents.common.hooks.payload import (
    HookPayload,
    extract_apply_patch_paths,
    normalize_claude,
    normalize_codex,
)
import agents.common.hooks.search_first as search_first_mod
from agents.common.hooks.index_refresh import check_index_refresh
from agents.common.hooks.listing_guard import is_bare_listing
import agents.common.hooks.post_edit_diff as post_edit_diff_mod
from agents.common.hooks.post_edit_diff import check_post_edit_diff
from agents.common.hooks.search_first import (
    check_search_first,
    is_indexed,
    search_was_recent,
)
from agents.common.hooks.truncate_output import check_truncate_output
from agents.common.hooks.compact_trigger import check_compact_trigger


# ---------------------------------------------------------------------------
# normalize_claude
# ---------------------------------------------------------------------------


class TestNormalizeClaude:
    def test_reads_tool_result(self):
        p = normalize_claude(
            {"tool_name": "Bash", "tool_input": {}, "tool_result": "out"}
        )
        assert p.agent == "claude"
        assert p.tool_output == "out"

    def test_falls_back_to_tool_response(self):
        p = normalize_claude(
            {"tool_name": "Read", "tool_input": {}, "tool_response": "content"}
        )
        assert p.tool_output == "content"

    def test_tool_result_preferred_over_tool_response(self):
        p = normalize_claude(
            {
                "tool_name": "Bash",
                "tool_input": {},
                "tool_result": "result",
                "tool_response": "response",
            }
        )
        assert p.tool_output == "result"

    def test_extracts_touched_files(self):
        p = normalize_claude(
            {
                "tool_name": "Edit",
                "tool_input": {"file_path": "/a/b.py"},
                "tool_result": "",
            }
        )
        assert p.touched_files == (Path("/a/b.py"),)

    def test_no_touched_files_without_file_path(self):
        p = normalize_claude({"tool_name": "Bash", "tool_input": {}, "tool_result": ""})
        assert p.touched_files == ()

    def test_transcript_path_parsed(self):
        p = normalize_claude(
            {
                "tool_name": "Bash",
                "tool_input": {},
                "tool_result": "",
                "transcript_path": "/tmp/t.json",
            }
        )
        assert p.transcript_path == Path("/tmp/t.json")

    def test_none_transcript_path(self):
        p = normalize_claude({"tool_name": "Bash", "tool_input": {}, "tool_result": ""})
        assert p.transcript_path is None

    def test_non_string_output_serialized(self):
        p = normalize_claude(
            {"tool_name": "Bash", "tool_input": {}, "tool_result": {"key": "val"}}
        )
        assert '"key"' in p.tool_output


# ---------------------------------------------------------------------------
# normalize_codex
# ---------------------------------------------------------------------------


class TestNormalizeCodex:
    def test_reads_tool_response_first(self):
        p = normalize_codex(
            {
                "tool_name": "Bash",
                "tool_input": {},
                "tool_response": "resp",
                "tool_result": "res",
            }
        )
        assert p.tool_output == "resp"

    def test_falls_back_to_tool_result(self):
        p = normalize_codex(
            {"tool_name": "Bash", "tool_input": {}, "tool_result": "result"}
        )
        assert p.tool_output == "result"

    def test_apply_patch_extracts_touched_files(self):
        p = normalize_codex(
            {
                "tool_name": "apply_patch",
                "tool_input": {
                    "patch": "*** Begin Patch\n*** Update File: a/b.py\n@@\n x\n*** End Patch\n"
                },
                "tool_response": "",
            }
        )
        assert p.touched_files == (Path("a/b.py"),)

    def test_extract_apply_patch_paths_handles_add_delete_move(self):
        patch = """*** Begin Patch
*** Add File: new.py
@@
+x
*** Delete File: old.py
*** Update File: moved.py
*** Move to: renamed.py
*** End Patch
"""
        assert extract_apply_patch_paths(patch) == (
            Path("new.py"),
            Path("old.py"),
            Path("moved.py"),
            Path("renamed.py"),
        )

    def test_edit_extracts_touched_files(self):
        p = normalize_codex(
            {
                "tool_name": "Edit",
                "tool_input": {"file_path": "/a/b.py"},
                "tool_response": "",
            }
        )
        assert p.touched_files == (Path("/a/b.py"),)

    def test_agent_field_is_codex(self):
        p = normalize_codex(
            {"tool_name": "Bash", "tool_input": {}, "tool_response": ""}
        )
        assert p.agent == "codex"

    def test_non_string_output_serialized(self):
        p = normalize_codex(
            {"tool_name": "Bash", "tool_input": {}, "tool_response": {"key": "val"}}
        )
        assert '"key"' in p.tool_output


# ---------------------------------------------------------------------------
# post-edit-diff
# ---------------------------------------------------------------------------


class TestPostEditDiff:
    def _apply_patch_payload(self) -> HookPayload:
        return HookPayload(
            agent="codex",
            tool_name="apply_patch",
            tool_input={},
            tool_output="",
            transcript_path=None,
            touched_files=(Path("src/app.py"),),
        )

    def test_apply_patch_context_starts_with_touched_files_and_summary(
        self, tmp_path, monkeypatch
    ):
        diff = [
            "diff --git a/src/app.py b/src/app.py\n",
            "--- a/src/app.py\n",
            "+++ b/src/app.py\n",
            "@@ -1,2 +1,2 @@\n",
            "-old\n",
            "+new\n",
        ]
        monkeypatch.setattr(
            post_edit_diff_mod, "diff_repo", lambda repo, pathspec=".": diff
        )

        code, stdout, stderr = check_post_edit_diff(
            self._apply_patch_payload(),
            repo=tmp_path,
            state_dir=tmp_path / "state",
            max_diff_lines=60,
            include_apply_patch=True,
            apply_patch_max_chars=10_000,
            message="Diff in context.",
        )

        assert code == 0
        assert stderr == ""
        ctx = json.loads(stdout)["hookSpecificOutput"]["additionalContext"]
        assert "apply_patch touched files:\n- src/app.py" in ctx
        assert "compact hunk summary:\n- src/app.py: 1 hunk(s), +1 -1" in ctx
        assert "full diff:" in ctx
        assert "+new" in ctx
        recorded = json.loads((tmp_path / "state" / "last-edit.json").read_text())
        assert str(tmp_path / "src/app.py") in recorded

    def test_apply_patch_omits_full_diff_over_codex_cap(self, tmp_path, monkeypatch):
        diff = [
            "diff --git a/src/app.py b/src/app.py\n",
            "--- a/src/app.py\n",
            "+++ b/src/app.py\n",
            "@@ -1,1 +1,1 @@\n",
            "-old\n",
            "+" + ("x" * 200) + "\n",
        ]
        monkeypatch.setattr(
            post_edit_diff_mod, "diff_repo", lambda repo, pathspec=".": diff
        )

        _, stdout, _ = check_post_edit_diff(
            self._apply_patch_payload(),
            repo=tmp_path,
            state_dir=tmp_path / "state",
            max_diff_lines=60,
            include_apply_patch=True,
            apply_patch_max_chars=80,
            message="Diff in context.",
        )

        ctx = json.loads(stdout)["hookSpecificOutput"]["additionalContext"]
        assert "compact hunk summary" in ctx
        assert "full diff omitted" in ctx
        assert "x" * 80 not in ctx

    def test_claude_edit_diff_ignores_apply_patch_cap(self, tmp_path):
        payload = HookPayload(
            agent="claude",
            tool_name="Edit",
            tool_input={
                "file_path": str(tmp_path / "app.py"),
                "old_string": "old\n",
                "new_string": "new\n",
            },
            tool_output="",
            transcript_path=None,
            touched_files=(tmp_path / "app.py",),
        )

        _, stdout, _ = check_post_edit_diff(
            payload,
            repo=tmp_path,
            state_dir=tmp_path / "state",
            max_diff_lines=60,
            include_apply_patch=False,
            apply_patch_max_chars=1,
            message="Diff in context.",
        )

        ctx = json.loads(stdout)["hookSpecificOutput"]["additionalContext"]
        assert "-old" in ctx
        assert "+new" in ctx
        assert "apply_patch touched files" not in ctx


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

    def test_zero_window_is_never_recent(self, tmp_path):
        (tmp_path / "last-search").touch()
        assert not search_was_recent(tmp_path, 0)

    def test_returns_false_when_stale(self, tmp_path):
        f = tmp_path / "last-search"
        f.touch()
        old = time.time() - 400
        os.utime(f, (old, old))
        assert not search_was_recent(tmp_path, 300)


# ---------------------------------------------------------------------------
# check_search_first
# ---------------------------------------------------------------------------


def _search_payload(tool: str, tool_input: dict | None = None) -> HookPayload:
    return HookPayload(
        agent="claude",
        tool_name=tool,
        tool_input=tool_input or {},
        tool_output="",
        transcript_path=None,
        touched_files=(),
    )


class TestCheckSearchFirst:
    def test_passes_non_read_tool(self, tmp_path):
        code, stdout, stderr = check_search_first(
            _search_payload("Bash"),
            repo=tmp_path,
            state_dir=tmp_path,
            config={},
        )
        assert (code, stdout, stderr) == (0, "", "")

    def test_passes_read_without_file_path(self, tmp_path):
        code, _, _ = check_search_first(
            _search_payload("Read"),
            repo=tmp_path,
            state_dir=tmp_path,
            config={},
        )
        assert code == 0

    def test_blocks_indexed_read_without_recent_search(self, tmp_path):
        readme = tmp_path / "README.md"
        readme.write_text("docs")
        code, _, stderr = check_search_first(
            _search_payload("Read", {"file_path": str(readme)}),
            repo=tmp_path,
            state_dir=tmp_path,
            config={"venv_py": "python", "tool_prefix": ".less_tokens/tools"},
        )
        assert code == 2
        assert "Search-first rule: README.md is indexed" in stderr
        assert ".less_tokens/tools/search.py" in stderr

    def test_grep_symbol_adds_context(self, tmp_path, monkeypatch):
        monkeypatch.setattr(search_first_mod, "_symbol_exists", lambda name, repo: True)
        code, stdout, stderr = check_search_first(
            _search_payload("Grep", {"pattern": "SomeSymbol"}),
            repo=tmp_path,
            state_dir=tmp_path,
            config={"venv_py": "python", "tool_prefix": ".less_tokens/tools"},
        )
        assert code == 0
        assert "SomeSymbol" in stdout
        assert "additionalContext" in stdout
        assert stderr == ""

    def test_grep_non_symbol_pattern_passes(self, tmp_path, monkeypatch):
        monkeypatch.setattr(search_first_mod, "_symbol_exists", lambda name, repo: True)
        code, stdout, stderr = check_search_first(
            _search_payload("Grep", {"pattern": "some-symbol"}),
            repo=tmp_path,
            state_dir=tmp_path,
            config={},
        )
        assert (code, stdout, stderr) == (0, "", "")


# ---------------------------------------------------------------------------
# check_index_refresh
# ---------------------------------------------------------------------------


class TestCheckIndexRefresh:
    def test_passes_unrelated_tool(self, tmp_path):
        code, stdout, stderr = check_index_refresh(
            _search_payload("Bash"),
            repo=tmp_path,
            state_dir=tmp_path / "state",
            config={},
        )
        assert (code, stdout, stderr) == (0, "", "")

    def test_skips_when_venv_missing(self, tmp_path):
        readme = tmp_path / "README.md"
        readme.write_text("docs")
        code, _, _ = check_index_refresh(
            _search_payload("Edit", {"file_path": str(readme)}),
            repo=tmp_path,
            state_dir=tmp_path / "state",
            config={"venv_py": tmp_path / "missing-python"},
        )
        assert code == 0
        assert not (tmp_path / "state" / "index-refresh.log").exists()

    def test_skips_local_refresh_for_external_search_backend(self, tmp_path):
        venv_py = tmp_path / ".venv" / "bin" / "python"
        venv_py.parent.mkdir(parents=True)
        venv_py.write_text("")
        tools = tmp_path / ".claude" / "tools"
        tools.mkdir(parents=True)
        (tools / "embeddings.py").write_text("")
        readme = tmp_path / "README.md"
        readme.write_text("docs")

        code, stdout, stderr = check_index_refresh(
            _search_payload("Edit", {"file_path": str(readme)}),
            repo=tmp_path,
            state_dir=tmp_path / "state",
            config={"venv_py": venv_py, "search_backend": "command"},
        )

        assert (code, stdout, stderr) == (0, "", "")
        assert not (tmp_path / "state" / "index-refresh.log").exists()

    def test_skips_unindexed_edit(self, tmp_path):
        venv_py = tmp_path / ".venv" / "bin" / "python"
        venv_py.parent.mkdir(parents=True)
        venv_py.write_text("")
        tools = tmp_path / ".claude" / "tools"
        tools.mkdir(parents=True)
        (tools / "embeddings.py").write_text("")
        nested = tmp_path / "src" / "module.py"
        nested.parent.mkdir()
        nested.write_text("print('not indexed by default')")

        check_index_refresh(
            _search_payload("Edit", {"file_path": str(nested)}),
            repo=tmp_path,
            state_dir=tmp_path / "state",
            config={"venv_py": venv_py},
        )

        assert not (tmp_path / "state" / "index-refresh.log").exists()

    def test_fires_refresh_for_indexed_edit(self, tmp_path, monkeypatch):
        calls = []

        class DummyPopen:
            def __init__(self, args, **kwargs):
                calls.append((args, kwargs))

        monkeypatch.setattr(
            "agents.common.hooks.index_refresh.subprocess.Popen", DummyPopen
        )
        venv_py = tmp_path / ".venv" / "bin" / "python"
        venv_py.parent.mkdir(parents=True)
        venv_py.write_text("")
        tools = tmp_path / ".claude" / "tools"
        tools.mkdir(parents=True)
        (tools / "embeddings.py").write_text("")
        readme = tmp_path / "README.md"
        readme.write_text("docs")

        code, stdout, stderr = check_index_refresh(
            _search_payload("Edit", {"file_path": str(readme)}),
            repo=tmp_path,
            state_dir=tmp_path / "state",
            config={"venv_py": venv_py},
        )

        assert (code, stdout, stderr) == (0, "", "")
        assert calls
        assert calls[0][0][:2] == [str(venv_py), str(tools / "embeddings.py")]
        assert (tmp_path / "state" / "index-refresh.log").exists()

    def test_apply_patch_fires_without_parsed_paths(self, tmp_path, monkeypatch):
        calls = []

        class DummyPopen:
            def __init__(self, args, **kwargs):
                calls.append(args)

        monkeypatch.setattr(
            "agents.common.hooks.index_refresh.subprocess.Popen", DummyPopen
        )
        venv_py = tmp_path / ".venv" / "bin" / "python"
        venv_py.parent.mkdir(parents=True)
        venv_py.write_text("")
        tools = tmp_path / ".less_tokens" / "tools"
        tools.mkdir(parents=True)
        (tools / "embeddings.py").write_text("")

        check_index_refresh(
            _search_payload("apply_patch"),
            repo=tmp_path,
            state_dir=tmp_path / "state",
            config={"venv_py": venv_py, "tool_prefix": ".less_tokens/tools"},
        )

        assert calls == [[str(venv_py), str(tools / "embeddings.py"), "refresh"]]

    def test_apply_patch_skips_when_parsed_paths_are_unindexed(
        self, tmp_path, monkeypatch
    ):
        calls = []

        class DummyPopen:
            def __init__(self, args, **kwargs):
                calls.append(args)

        monkeypatch.setattr(
            "agents.common.hooks.index_refresh.subprocess.Popen", DummyPopen
        )
        venv_py = tmp_path / ".venv" / "bin" / "python"
        venv_py.parent.mkdir(parents=True)
        venv_py.write_text("")
        tools = tmp_path / ".less_tokens" / "tools"
        tools.mkdir(parents=True)
        (tools / "embeddings.py").write_text("")

        check_index_refresh(
            HookPayload(
                agent="codex",
                tool_name="apply_patch",
                tool_input={},
                tool_output="",
                transcript_path=None,
                touched_files=(Path("assets/logo.png"),),
            ),
            repo=tmp_path,
            state_dir=tmp_path / "state",
            config={"venv_py": venv_py, "tool_prefix": ".less_tokens/tools"},
        )

        assert calls == []

    def test_apply_patch_fires_when_parsed_path_is_indexed(self, tmp_path, monkeypatch):
        calls = []

        class DummyPopen:
            def __init__(self, args, **kwargs):
                calls.append(args)

        monkeypatch.setattr(
            "agents.common.hooks.index_refresh.subprocess.Popen", DummyPopen
        )
        venv_py = tmp_path / ".venv" / "bin" / "python"
        venv_py.parent.mkdir(parents=True)
        venv_py.write_text("")
        tools = tmp_path / ".less_tokens" / "tools"
        tools.mkdir(parents=True)
        (tools / "embeddings.py").write_text("")

        check_index_refresh(
            HookPayload(
                agent="codex",
                tool_name="apply_patch",
                tool_input={},
                tool_output="",
                transcript_path=None,
                touched_files=(Path("README.md"),),
            ),
            repo=tmp_path,
            state_dir=tmp_path / "state",
            config={"venv_py": venv_py, "tool_prefix": ".less_tokens/tools"},
        )

        assert calls == [[str(venv_py), str(tools / "embeddings.py"), "refresh"]]


# ---------------------------------------------------------------------------
# check_truncate_output
# ---------------------------------------------------------------------------


def _payload(tool: str, output: str) -> HookPayload:
    return HookPayload(
        agent="claude",
        tool_name=tool,
        tool_input={},
        tool_output=output,
        transcript_path=None,
        touched_files=(),
    )


class TestCheckTruncateOutput:
    def test_passes_small_bash(self):
        code, _, _ = check_truncate_output(
            _payload("Bash", "x" * 100),
            max_chars=4000,
            head_lines=50,
            tail_lines=20,
            max_glob_results=100,
        )
        assert code == 0

    def test_truncates_large_bash(self):
        code, stdout, _ = check_truncate_output(
            _payload("Bash", "x" * 10_000),
            max_chars=4000,
            head_lines=50,
            tail_lines=20,
            max_glob_results=100,
        )
        assert code == 2
        assert "omitted" in stdout

    def test_passes_unrelated_tool(self):
        code, _, _ = check_truncate_output(
            _payload("Edit", "x" * 10_000),
            max_chars=4000,
            head_lines=50,
            tail_lines=20,
            max_glob_results=100,
        )
        assert code == 0

    def test_disabled_when_max_chars_zero(self):
        code, _, _ = check_truncate_output(
            _payload("Bash", "x" * 10_000),
            max_chars=0,
            head_lines=50,
            tail_lines=20,
            max_glob_results=100,
        )
        assert code == 0

    def test_glob_line_cap(self):
        lines = "\n".join(f"file{i}.py" for i in range(200))
        code, stdout, _ = check_truncate_output(
            _payload("Glob", lines),
            max_chars=0,
            head_lines=50,
            tail_lines=20,
            max_glob_results=10,
        )
        assert code == 2
        assert "more file" in stdout

    def test_read_truncated_by_char_ceiling(self):
        code, stdout, _ = check_truncate_output(
            _payload("Read", "x" * 10_000),
            max_chars=4000,
            head_lines=50,
            tail_lines=20,
            max_glob_results=100,
        )
        assert code == 2
        assert len(stdout) <= 5000


# ---------------------------------------------------------------------------
# listing_guard
# ---------------------------------------------------------------------------


class TestListingGuard:
    def test_broad_git_diff_is_not_shared_claude_listing_rule(self):
        intercepted, _ = is_bare_listing("git diff")
        assert not intercepted


# ---------------------------------------------------------------------------
# check_compact_trigger
# ---------------------------------------------------------------------------


def _compact_payload(transcript_path=None) -> HookPayload:
    return HookPayload(
        agent="claude",
        tool_name="Bash",
        tool_input={},
        tool_output="",
        transcript_path=transcript_path,
        touched_files=(),
    )


class TestCheckCompactTrigger:
    def test_passes_when_disabled(self, tmp_path):
        code, _, _ = check_compact_trigger(
            _compact_payload(), state_dir=tmp_path, max_session_chars=0, message="msg"
        )
        assert code == 0

    def test_passes_when_no_transcript(self, tmp_path):
        code, _, _ = check_compact_trigger(
            _compact_payload(), state_dir=tmp_path, max_session_chars=100, message="msg"
        )
        assert code == 0

    def test_fires_when_transcript_exceeds_threshold(self, tmp_path):
        transcript = tmp_path / "session.json"
        transcript.write_text("x" * 1000)
        code, _, stderr = check_compact_trigger(
            _compact_payload(transcript),
            state_dir=tmp_path,
            max_session_chars=100,
            message="Session is {size:,} chars.",
        )
        assert code == 2
        assert "1,000" in stderr

    def test_writes_state_file_on_fire(self, tmp_path):
        transcript = tmp_path / "session.json"
        transcript.write_text("x" * 1000)
        check_compact_trigger(
            _compact_payload(transcript),
            state_dir=tmp_path,
            max_session_chars=100,
            message="msg",
        )
        assert (tmp_path / "compact-trigger-last").exists()

    def test_hysteresis_suppresses_repeat_fire(self, tmp_path):
        transcript = tmp_path / "session.json"
        transcript.write_text("x" * 1000)
        (tmp_path / "compact-trigger-last").write_text("999")
        code, _, _ = check_compact_trigger(
            _compact_payload(transcript),
            state_dir=tmp_path,
            max_session_chars=100,
            message="msg",
        )
        assert code == 0
