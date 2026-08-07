from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "tools"))
import claudemd_audit as audit_mod  # noqa: E402
import instruction_prune as prune_mod  # noqa: E402


REPO = Path(__file__).resolve().parent.parent.parent.parent
TOOL = REPO / ".claude" / "tools" / "instruction_prune.py"


@pytest.fixture(autouse=True)
def _no_duplication_index(monkeypatch):
    # Force the size-based REVIEW fallback deterministically -- whether a real
    # fastembed/index.db is available locally shouldn't change what these
    # pruning-mechanics tests exercise (that's claudemd_audit's own test's job).
    monkeypatch.setattr(audit_mod, "duplication", lambda sections: None)


BIG_SECTION = "## Architecture deep dive\n" + ("word " * 300) + "\n"


def _write_claude_md(tmp_path: Path) -> Path:
    p = tmp_path / "CLAUDE.md"
    p.write_text(
        "# CLAUDE.md\n\n## Keep this\nShort standing rule.\n\n" + BIG_SECTION,
        encoding="utf-8",
    )
    return p


def test_plan_moves_flags_big_section_review_only(tmp_path):
    path = _write_claude_md(tmp_path)
    with patch.object(audit_mod, "BASE", tmp_path):
        moves = prune_mod.plan_moves(path)
    assert [m["title"] for m in moves] == ["Architecture deep dive"]
    assert moves[0]["verdict"].startswith("REVIEW")


def test_dry_run_does_not_mutate_files(tmp_path, capsys):
    path = _write_claude_md(tmp_path)
    doc = tmp_path / "DOCUMENTATION.md"
    doc.write_text("# Documentation\n", encoding="utf-8")
    before = path.read_text(encoding="utf-8")

    with (
        patch.object(audit_mod, "BASE", tmp_path),
        patch.object(prune_mod, "BASE", tmp_path),
    ):
        rc = prune_mod.main(["--agent", "claude", "--budget", "50"])

    assert rc == 0
    assert path.read_text(encoding="utf-8") == before
    assert doc.read_text(encoding="utf-8") == "# Documentation\n"
    out = capsys.readouterr().out
    assert "MOVE" in out
    assert "Architecture deep dive" in out


def test_apply_moves_section_and_leaves_pointer(tmp_path):
    path = _write_claude_md(tmp_path)
    doc = tmp_path / "DOCUMENTATION.md"
    doc.write_text("# Documentation\nExisting.\n", encoding="utf-8")

    with (
        patch.object(audit_mod, "BASE", tmp_path),
        patch.object(prune_mod, "BASE", tmp_path),
    ):
        rc = prune_mod.main(["--agent", "claude", "--budget", "50", "--apply"])

    assert rc == 0
    after = path.read_text(encoding="utf-8")
    assert "## Architecture deep dive" not in after  # the section itself is gone
    assert "_Moved to DOCUMENTATION.md → Architecture deep dive._" in after
    assert "Keep this" in after  # untouched section survives

    overflow = doc.read_text(encoding="utf-8")
    assert "## Moved from CLAUDE.md" in overflow
    assert "## Architecture deep dive" in overflow
    assert "Existing." in overflow  # prior content preserved


def test_apply_no_pointer_leaves_no_trace(tmp_path):
    path = _write_claude_md(tmp_path)
    doc = tmp_path / "DOCUMENTATION.md"
    doc.write_text("# Documentation\n", encoding="utf-8")

    with (
        patch.object(audit_mod, "BASE", tmp_path),
        patch.object(prune_mod, "BASE", tmp_path),
    ):
        rc = prune_mod.main(
            ["--agent", "claude", "--budget", "50", "--apply", "--no-pointer"]
        )

    assert rc == 0
    after = path.read_text(encoding="utf-8")
    assert "Architecture deep dive" not in after
    assert "Moved to" not in after


def test_apply_clears_over_budget_when_offending_section_moves(tmp_path):
    path = _write_claude_md(tmp_path)
    doc = tmp_path / "DOCUMENTATION.md"
    doc.write_text("# Documentation\n", encoding="utf-8")

    with patch.object(audit_mod, "BASE", tmp_path):
        before = audit_mod.audit(path, budget=50)
        assert before["over_budget"] is True

        with patch.object(prune_mod, "BASE", tmp_path):
            prune_mod.main(["--agent", "claude", "--budget", "50", "--apply"])

        after = audit_mod.audit(path, budget=50)
    assert after["over_budget"] is False
    assert after["dead_refs"] == []


def test_verify_recall_pass_and_fail(tmp_path):
    path = _write_claude_md(tmp_path)
    doc = tmp_path / "DOCUMENTATION.md"
    doc.write_text("# Documentation\n", encoding="utf-8")

    class FakeSearch:
        @staticmethod
        def _index_is_stale():
            return False

        @staticmethod
        def search(query, k=5):
            if query == "Architecture deep dive":
                return [{"source_path": "DOCUMENTATION.md"}]
            return []

    class FakeEmbeddings:
        @staticmethod
        def refresh():
            return 0

    with (
        patch.object(prune_mod, "search_mod", FakeSearch),
        patch.object(prune_mod, "embeddings_mod", FakeEmbeddings),
    ):
        results = prune_mod.verify_recall(
            ["Architecture deep dive"], "DOCUMENTATION.md"
        )
        assert results == [{"title": "Architecture deep dive", "passed": True}]

        fail_results = prune_mod.verify_recall(
            ["Nonexistent topic"], "DOCUMENTATION.md"
        )
        assert fail_results == [{"title": "Nonexistent topic", "passed": False}]


def test_apply_verify_recall_fail_returns_exit_1(tmp_path):
    path = _write_claude_md(tmp_path)
    doc = tmp_path / "DOCUMENTATION.md"
    doc.write_text("# Documentation\n", encoding="utf-8")

    class FakeSearch:
        @staticmethod
        def _index_is_stale():
            return False

        @staticmethod
        def search(query, k=5):
            return []  # nothing ever found -> FAIL

    class FakeEmbeddings:
        @staticmethod
        def refresh():
            return 0

    with (
        patch.object(audit_mod, "BASE", tmp_path),
        patch.object(prune_mod, "BASE", tmp_path),
        patch.object(prune_mod, "search_mod", FakeSearch),
        patch.object(prune_mod, "embeddings_mod", FakeEmbeddings),
    ):
        rc = prune_mod.main(
            ["--agent", "claude", "--budget", "50", "--apply", "--verify-recall"]
        )

    assert rc == 1


def test_apply_verify_recall_missing_numpy_returns_clean_exit_2(tmp_path, capsys):
    path = _write_claude_md(tmp_path)
    doc = tmp_path / "DOCUMENTATION.md"
    doc.write_text("# Documentation\n", encoding="utf-8")

    def _raise(*args, **kwargs):
        raise ModuleNotFoundError("No module named 'numpy'", name="numpy")

    with (
        patch.object(audit_mod, "BASE", tmp_path),
        patch.object(prune_mod, "BASE", tmp_path),
        patch.object(prune_mod, "verify_recall", _raise),
    ):
        rc = prune_mod.main(
            ["--agent", "claude", "--budget", "50", "--apply", "--verify-recall"]
        )

    assert rc == 2
    err = capsys.readouterr().err
    assert "numpy" in err
    assert ".venv-tokens" in err


def test_cli_agent_codex_targets_agents_md(tmp_path):
    agents_md = tmp_path / "AGENTS.md"
    agents_md.write_text("# AGENTS.md\n\n## Keep\nrule\n", encoding="utf-8")
    (tmp_path / "DOCUMENTATION.md").write_text("# Documentation\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "--agent",
            "codex",
            "--path",
            str(agents_md),
            "--json",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(REPO / ".claude" / "tools")},
        timeout=10,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["agent"] == "codex"
    assert payload["path"] == str(agents_md)


def test_cli_missing_doc_exits_2(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "--agent",
            "claude",
            "--path",
            str(tmp_path / "CLAUDE.md"),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(REPO / ".claude" / "tools")},
        timeout=10,
    )
    assert result.returncode == 2
