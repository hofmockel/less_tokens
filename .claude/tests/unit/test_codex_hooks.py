"""Codex adapter hook subprocess tests — stdin/stdout/exit-code contract."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent.parent.parent
CODEX_HOOKS = REPO / "agents" / "codex" / "hooks"

_ENV = {
    **os.environ,
    "PYTHONPATH": os.pathsep.join((
        str(REPO / ".claude" / "tests"),
        str(REPO / ".claude" / "tools"),
        os.environ.get("PYTHONPATH", ""),
    )),
    "LESS_TOKENS_REPO": str(REPO),
}


def run_hook_with_env(hook_name: str, payload: dict, extra_env: dict | None = None) -> tuple[int, str, str]:
    env = {**_ENV, **(extra_env or {})}
    result = subprocess.run(
        [sys.executable, str(CODEX_HOOKS / hook_name)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
    )
    return result.returncode, result.stdout, result.stderr


def _records(state_dir: Path) -> list[dict]:
    log = state_dir / "savings.jsonl"
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text().splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# index-refresh.py
# ---------------------------------------------------------------------------

class TestCodexIndexRefresh:
    def test_apply_patch_exits_zero(self):
        """apply_patch always exits 0 — no VENV_PY check skips early."""
        code, _, _ = run_hook_with_env("index-refresh.py", {
            "tool_name": "apply_patch",
            "tool_input": {},
            "tool_response": "",
        })
        assert code == 0

    def test_unrelated_tool_exits_zero(self):
        code, _, _ = run_hook_with_env("index-refresh.py", {
            "tool_name": "Bash",
            "tool_input": {},
            "tool_response": "some output",
        })
        assert code == 0

    def test_edit_with_non_indexed_file_exits_zero(self, tmp_path):
        non_indexed = tmp_path / "binary.exe"
        non_indexed.touch()
        code, _, _ = run_hook_with_env("index-refresh.py", {
            "tool_name": "Edit",
            "tool_input": {"file_path": str(non_indexed)},
            "tool_response": "",
        })
        assert code == 0


# ---------------------------------------------------------------------------
# truncate-output.py
# ---------------------------------------------------------------------------

class TestCodexTruncateOutput:
    def test_passes_small_output(self):
        code, _, _ = run_hook_with_env("truncate-output.py", {
            "tool_name": "Bash",
            "tool_response": "small output",
        })
        assert code == 0

    def test_truncates_large_tool_response(self):
        code, stdout, stderr = run_hook_with_env("truncate-output.py", {
            "tool_name": "Bash",
            "tool_response": "x" * 10_000,
        })
        assert code == 2
        assert "omitted" in stdout or "omitted" in stderr
        assert len(stdout) < 2_000

    def test_passes_non_targeted_tool(self):
        code, _, _ = run_hook_with_env("truncate-output.py", {
            "tool_name": "Edit",
            "tool_response": "x" * 10_000,
        })
        assert code == 0

    def test_truncates_large_filesystem_read(self):
        code, stdout, _ = run_hook_with_env("truncate-output.py", {
            "tool_name": "mcp__filesystem__read_file",
            "tool_response": "x" * 10_000,
        })
        assert code == 2
        assert "omitted" in stdout
        assert len(stdout) < 1_600

    def test_env_override_sets_bash_cap(self):
        code, stdout, _ = run_hook_with_env("truncate-output.py", {
            "tool_name": "Bash",
            "tool_response": "x" * 10_000,
        }, extra_env={"LESS_TOKENS_CODEX_MAX_TOOL_OUTPUT_CHARS": "900"})
        assert code == 2
        assert "omitted" in stdout
        assert len(stdout) < 1_200

    def test_env_override_sets_filesystem_read_cap(self):
        code, stdout, _ = run_hook_with_env("truncate-output.py", {
            "tool_name": "mcp__filesystem__read_file",
            "tool_response": "x" * 10_000,
        }, extra_env={"LESS_TOKENS_CODEX_MAX_FILESYSTEM_READ_CHARS": "700"})
        assert code == 2
        assert "omitted" in stdout
        assert len(stdout) < 1_000

    def test_logs_measured_savings(self, tmp_path):
        state_dir = tmp_path / "state"
        code, stdout, _ = run_hook_with_env("truncate-output.py", {
            "tool_name": "Bash",
            "tool_response": "x" * 10_000,
            "session_id": "codex-sess",
        }, extra_env={"LESS_TOKENS_STATE_DIR": str(state_dir)})

        assert code == 2
        recs = _records(state_dir)
        assert len(recs) == 1
        rec = recs[0]
        assert rec["strategy"] == "truncation"
        assert rec["basis"] == "measured"
        kept = len(stdout.rstrip("\n"))
        assert rec["kept_chars"] == kept
        assert rec["elided_chars"] == 10_000 - kept
        assert rec["session_id"] == "codex-sess"


# ---------------------------------------------------------------------------
# terse-reminder.py
# ---------------------------------------------------------------------------

class TestCodexTerseReminder:
    def test_passes_concise_response(self):
        code, _, _ = run_hook_with_env("terse-reminder.py", {
            "response": "Done. Tests pass.",
        })
        assert code == 0

    def test_blocks_filler_response(self):
        code, _, stderr = run_hook_with_env("terse-reminder.py", {
            "response": "Certainly. Of course, I hope this helps.",
        })
        assert code == 2
        assert "filler phrases detected" in stderr

    def test_blocks_single_filler_response(self):
        code, _, stderr = run_hook_with_env("terse-reminder.py", {
            "response": "Certainly.",
        })
        assert code == 2
        assert "filler phrases detected" in stderr

    def test_ignores_non_string_response(self):
        code, _, _ = run_hook_with_env("terse-reminder.py", {
            "response": {"text": "Certainly. Of course."},
        })
        assert code == 0

    def test_stop_hook_active_guard_exits_zero(self):
        code, _, _ = run_hook_with_env("terse-reminder.py", {
            "stop_hook_active": True,
            "response": "Certainly.",
        })
        assert code == 0

    def test_document_draft_sentinel_exempts_response(self):
        code, _, _ = run_hook_with_env("terse-reminder.py", {
            "response": "<!-- less-tokens: document-draft -->\nCertainly. Of course, I hope this helps.",
        })
        assert code == 0


# ---------------------------------------------------------------------------
# compact-trigger.py
# ---------------------------------------------------------------------------

class TestCodexCompactTrigger:
    def test_fires_with_large_transcript(self, tmp_path):
        transcript = tmp_path / "session.json"
        transcript.write_text("x" * 800_000)
        state_dir = tmp_path / "state"

        code, _, stderr = run_hook_with_env("compact-trigger.py", {
            "tool_name": "Bash",
            "tool_input": {},
            "tool_response": "",
            "transcript_path": str(transcript),
        }, extra_env={"LESS_TOKENS_STATE_DIR": str(state_dir)})

        assert code == 2
        assert "/compact" not in stderr
        assert "Codex" in stderr or "session" in stderr.lower()

    def test_passes_without_transcript(self):
        code, _, _ = run_hook_with_env("compact-trigger.py", {
            "tool_name": "Bash",
            "tool_input": {},
            "tool_response": "",
        })
        assert code == 0

    def test_message_does_not_contain_slash_compact(self, tmp_path):
        transcript = tmp_path / "session.json"
        transcript.write_text("x" * 800_000)
        state_dir = tmp_path / "state"

        _, _, stderr = run_hook_with_env("compact-trigger.py", {
            "tool_name": "Bash",
            "tool_input": {},
            "tool_response": "",
            "transcript_path": str(transcript),
        }, extra_env={"LESS_TOKENS_STATE_DIR": str(state_dir)})

        assert "/compact" not in stderr

    def test_logs_measured_compaction_when_transcript_shrinks(self, tmp_path):
        transcript = tmp_path / "session.json"
        transcript.write_text("x" * 800_000)
        state_dir = tmp_path / "state"

        run_hook_with_env("compact-trigger.py", {
            "tool_name": "Bash",
            "tool_input": {},
            "tool_response": "",
            "transcript_path": str(transcript),
            "session_id": "codex-sess",
        }, extra_env={"LESS_TOKENS_STATE_DIR": str(state_dir)})

        transcript.write_text("x" * 40_000)
        code, _, _ = run_hook_with_env("compact-trigger.py", {
            "tool_name": "Bash",
            "tool_input": {},
            "tool_response": "",
            "transcript_path": str(transcript),
            "session_id": "codex-sess",
        }, extra_env={"LESS_TOKENS_STATE_DIR": str(state_dir)})

        assert code == 0
        recs = _records(state_dir)
        assert len(recs) == 1
        rec = recs[0]
        assert rec["strategy"] == "compaction"
        assert rec["basis"] == "measured"
        assert rec["kept_chars"] == 40_000
        assert rec["elided_chars"] == 800_000 - 40_000
        assert rec["session_id"] == "codex-sess"


# ---------------------------------------------------------------------------
# search-first.py
# ---------------------------------------------------------------------------

class TestCodexSearchFirst:
    def test_unknown_tool_exits_zero(self, tmp_path):
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        code, _, _ = run_hook_with_env("search-first.py", {
            "tool_name": "UnknownFutureTool",
            "tool_input": {},
            "tool_response": "",
        }, extra_env={"LESS_TOKENS_STATE_DIR": str(state_dir)})
        assert code == 0

    def test_logs_upper_bound_when_blocking_indexed_read(self, tmp_path):
        state_dir = tmp_path / "state"
        code, _, stderr = run_hook_with_env("search-first.py", {
            "tool_name": "mcp__filesystem__read_file",
            "tool_input": {"path": str(REPO / "README.md")},
            "tool_response": "",
            "session_id": "codex-sess",
        }, extra_env={"LESS_TOKENS_STATE_DIR": str(state_dir)})

        assert code == 2
        assert "Search-first rule" in stderr
        recs = _records(state_dir)
        assert len(recs) == 1
        rec = recs[0]
        assert rec["strategy"] == "search-blocked"
        assert rec["basis"] == "upper_bound"
        assert rec["kept_chars"] == 0
        assert rec["elided_chars"] == (REPO / "README.md").stat().st_size
        assert rec["where"] == "README.md"
        assert rec["session_id"] == "codex-sess"


# ---------------------------------------------------------------------------
# read-guard.py
# ---------------------------------------------------------------------------

class TestCodexReadGuard:
    def test_blocks_lockfile_filesystem_read(self, tmp_path):
        p = tmp_path / "package-lock.json"
        p.write_text("{}")
        code, _, stderr = run_hook_with_env("read-guard.py", {
            "tool_name": "mcp__filesystem__read_file",
            "tool_input": {"path": str(p)},
            "tool_response": "",
        })
        assert code == 2
        assert "Read-guard" in stderr

    def test_allows_sliced_lockfile_read(self, tmp_path):
        p = tmp_path / "package-lock.json"
        p.write_text("{}")
        code, _, _ = run_hook_with_env("read-guard.py", {
            "tool_name": "mcp__filesystem__read_file",
            "tool_input": {"path": str(p), "offset": 1},
            "tool_response": "",
        })
        assert code == 0


# ---------------------------------------------------------------------------
# auto-slice.py
# ---------------------------------------------------------------------------

class TestCodexAutoSlice:
    def test_blocks_read_with_recent_search_range(self, tmp_path):
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        (state_dir / "last-search.json").write_text(json.dumps({"src/app.py": [[5, 9]]}))
        code, _, stderr = run_hook_with_env("auto-slice.py", {
            "tool_name": "mcp__filesystem__read_file",
            "tool_input": {"path": "/repo/src/app.py"},
            "tool_response": "",
        }, extra_env={"LESS_TOKENS_STATE_DIR": str(state_dir)})
        assert code == 2
        assert "Auto-slice" in stderr
        assert "offset=5" in stderr or "offset=5" in stderr.replace(" ", "")


# ---------------------------------------------------------------------------
# grep-first-read.py
# ---------------------------------------------------------------------------

class TestCodexGrepFirstRead:
    def test_blocks_large_nonindexed_file(self, tmp_path):
        p = tmp_path / "large.txt"
        p.write_text("\n".join(str(i) for i in range(250)))
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        code, _, stderr = run_hook_with_env("grep-first-read.py", {
            "tool_name": "mcp__filesystem__read_file",
            "tool_input": {"path": str(p)},
            "tool_response": "",
        }, extra_env={"LESS_TOKENS_STATE_DIR": str(state_dir)})
        assert code == 2
        assert "Grep-first" in stderr

    def test_allows_sliced_large_file(self, tmp_path):
        p = tmp_path / "large.txt"
        p.write_text("\n".join(str(i) for i in range(250)))
        code, _, _ = run_hook_with_env("grep-first-read.py", {
            "tool_name": "mcp__filesystem__read_file",
            "tool_input": {"path": str(p), "offset": 10},
            "tool_response": "",
        })
        assert code == 0


# ---------------------------------------------------------------------------
# post-edit-diff.py / read-after-edit.py
# ---------------------------------------------------------------------------

class TestCodexPostEditAndReadAfterEdit:
    def test_post_edit_records_last_edit(self, tmp_path):
        state_dir = tmp_path / "state"
        target = tmp_path / "app.py"
        target.write_text("new")
        code, stdout, _ = run_hook_with_env("post-edit-diff.py", {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(target),
                "old_string": "old\n",
                "new_string": "new\n",
            },
            "tool_response": "",
        }, extra_env={"LESS_TOKENS_STATE_DIR": str(state_dir)})
        assert code == 0
        assert "post-edit-diff" in stdout
        data = json.loads((state_dir / "last-edit.json").read_text())
        assert str(target.resolve()) in data

    def test_read_after_edit_blocks_recent_reread(self, tmp_path):
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        target = tmp_path / "app.py"
        target.write_text("new")
        (state_dir / "last-edit.json").write_text(json.dumps({str(target.resolve()): __import__("time").time()}))
        code, _, stderr = run_hook_with_env("read-after-edit.py", {
            "tool_name": "mcp__filesystem__read_file",
            "tool_input": {"path": str(target)},
            "tool_response": "",
        }, extra_env={"LESS_TOKENS_STATE_DIR": str(state_dir)})
        assert code == 2
        assert "read-after-edit" in stderr


# ---------------------------------------------------------------------------
# listing-guard.py / lean-output.py / context-cache.py
# ---------------------------------------------------------------------------

class TestCodexBashAndCacheAdapters:
    def test_listing_guard_blocks_recursive_ls(self):
        code, stdout, _ = run_hook_with_env("listing-guard.py", {
            "tool_name": "Bash",
            "tool_input": {"command": "ls -R ."},
            "tool_response": "",
        })
        assert code == 2
        assert "listing-guard" in stdout

    def test_listing_guard_rewrites_bare_find(self):
        code, stdout, _ = run_hook_with_env("listing-guard.py", {
            "tool_name": "Bash",
            "tool_input": {"command": "find ."},
            "tool_response": "",
        })
        assert code == 2
        assert "rg --files" in stdout

    def test_listing_guard_blocks_broad_git_diff(self):
        code, stdout, _ = run_hook_with_env("listing-guard.py", {
            "tool_name": "Bash",
            "tool_input": {"command": "git diff"},
            "tool_response": "",
        })
        assert code == 2
        assert "git diff --stat" in stdout
        assert "git diff --name-only" in stdout

    def test_listing_guard_blocks_verbose_pytest(self):
        code, stdout, _ = run_hook_with_env("listing-guard.py", {
            "tool_name": "Bash",
            "tool_input": {"command": "pytest -vv"},
            "tool_response": "",
        })
        assert code == 2
        assert "pytest -q" in stdout

    def test_listing_guard_blocks_broad_cat(self):
        code, stdout, _ = run_hook_with_env("listing-guard.py", {
            "tool_name": "Bash",
            "tool_input": {"command": "cat README.md"},
            "tool_response": "",
        })
        assert code == 2
        assert "sed -n" in stdout

    def test_lean_output_parses_pytest_failure(self):
        raw = (
            "\n".join(f"noise line {i}" for i in range(40))
            + "\nFAILED tests/test_x.py::test_y - AssertionError\n"
            + "E   assert 1 == 2\n"
            + "=== 1 failed in 0.01s ===\n"
        )
        code, stdout, _ = run_hook_with_env("lean-output.py", {
            "tool_name": "Bash",
            "tool_input": {"command": "pytest"},
            "tool_response": raw,
        })
        assert code == 0
        assert "lean-output:pytest" in stdout
        assert "FAILED tests/test_x.py::test_y" in stdout

    def test_context_cache_blocks_repeat_read(self, tmp_path):
        # Record happens only on PostToolUse (BACKLOG.md: a PreToolUse-only
        # record falsely marks a sibling-hook-denied Read as served), so the
        # actual-execution Post call must run between the two Pre checks.
        state_dir = tmp_path / "state"
        target = tmp_path / "app.py"
        target.write_text("print(1)\n")
        pre = {
            "hook_event_name": "PreToolUse",
            "tool_name": "mcp__filesystem__read_file",
            "tool_input": {"path": str(target)},
            "transcript_path": str(tmp_path / "transcript.jsonl"),
        }
        post = {
            "hook_event_name": "PostToolUse",
            "tool_name": "mcp__filesystem__read_file",
            "tool_input": {"path": str(target)},
            "tool_response": "print(1)\n",
            "transcript_path": str(tmp_path / "transcript.jsonl"),
        }
        code1, _, _ = run_hook_with_env("context-cache.py", pre, extra_env={"LESS_TOKENS_STATE_DIR": str(state_dir)})
        code_post, _, _ = run_hook_with_env("context-cache.py", post, extra_env={"LESS_TOKENS_STATE_DIR": str(state_dir)})
        code2, _, stderr2 = run_hook_with_env("context-cache.py", pre, extra_env={"LESS_TOKENS_STATE_DIR": str(state_dir)})
        assert code1 == 0
        assert code_post == 0
        assert code2 == 2
        assert "context-cache" in stderr2

    def test_context_cache_denied_read_is_not_recorded_as_served(self, tmp_path):
        """A Read denied by a sibling PreToolUse hook (never executed) must
        not be recorded — PostToolUse never fires for a denied call, so a
        repeat PreToolUse check must still pass (BACKLOG.md)."""
        state_dir = tmp_path / "state"
        target = tmp_path / "app.py"
        target.write_text("print(1)\n")
        pre = {
            "hook_event_name": "PreToolUse",
            "tool_name": "mcp__filesystem__read_file",
            "tool_input": {"path": str(target)},
            "transcript_path": str(tmp_path / "transcript.jsonl"),
        }
        # Only the PreToolUse pass runs (simulating a sibling hook's deny —
        # the tool never executes, so PostToolUse never fires).
        code1, _, _ = run_hook_with_env("context-cache.py", pre, extra_env={"LESS_TOKENS_STATE_DIR": str(state_dir)})
        code2, _, _ = run_hook_with_env("context-cache.py", pre, extra_env={"LESS_TOKENS_STATE_DIR": str(state_dir)})
        assert code1 == 0
        assert code2 == 0, "a denied Read must not be recorded as served"

    def test_context_cache_blocks_repeat_bash_after_posttool_record(self, tmp_path):
        state_dir = tmp_path / "state"
        post = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "pwd"},
            "tool_response": str(tmp_path),
            "transcript_path": str(tmp_path / "transcript.jsonl"),
        }
        pre = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "pwd"},
            "transcript_path": str(tmp_path / "transcript.jsonl"),
        }
        code1, _, _ = run_hook_with_env("context-cache.py", post, extra_env={"LESS_TOKENS_STATE_DIR": str(state_dir)})
        code2, _, stderr2 = run_hook_with_env("context-cache.py", pre, extra_env={"LESS_TOKENS_STATE_DIR": str(state_dir)})
        assert code1 == 0
        assert code2 == 2
        assert "Bash `pwd` already ran" in stderr2

    def test_filesystem_read_of_indexed_file_is_checked(self, tmp_path):
        """mcp__filesystem__read_file on an indexed file with no recent search is blocked."""
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        code, _, _ = run_hook_with_env("search-first.py", {
            "tool_name": "mcp__filesystem__read_file",
            "tool_input": {"path": str(REPO / "README.md")},
            "tool_response": "",
        }, extra_env={"LESS_TOKENS_STATE_DIR": str(state_dir)})
        assert code == 2

    def test_gate_clears_after_recent_search(self, tmp_path):
        """Gate passes when last-search sentinel is present in the state dir."""
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        (state_dir / "last-search").touch()
        code, _, _ = run_hook_with_env("search-first.py", {
            "tool_name": "mcp__filesystem__read_file",
            "tool_input": {"path": str(REPO / "README.md")},
            "tool_response": "",
        }, extra_env={"LESS_TOKENS_STATE_DIR": str(state_dir)})
        assert code == 0
