"""Shared continue.md freshness-gate tests."""
from __future__ import annotations

import subprocess
from pathlib import Path

from agents.common.hooks.continue_freshness import check_continue_freshness


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _commit(repo: Path, message: str) -> str:
    marker = repo / "marker.txt"
    marker.write_text(message, encoding="utf-8")
    _git(repo, "add", "marker.txt")
    _git(repo, "commit", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def _repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "tests@example.invalid")
    _git(repo, "config", "user.name", "less_tokens tests")
    return repo, _commit(repo, "first")


def _handoff(repo: Path, recorded: str) -> Path:
    path = repo / "continue.md"
    path.write_text(
        f"# Continue\n\n_Last updated at HEAD `{recorded}` on 2026-07-16._\n",
        encoding="utf-8",
    )
    return path


def test_fresh_handoff_passes(tmp_path):
    repo, head = _repo(tmp_path)
    handoff = _handoff(repo, head)

    assert check_continue_freshness(str(handoff), repo=repo) == (0, "", "")


def test_stale_handoff_blocks_with_commit_preview(tmp_path):
    repo, recorded = _repo(tmp_path)
    handoff = _handoff(repo, recorded)
    _commit(repo, "second")

    code, stdout, stderr = check_continue_freshness(str(handoff), repo=repo)

    assert code == 2
    assert stdout == ""
    assert "1 commit(s) stale" in stderr
    assert "second" in stderr
    assert f"git log --oneline {recorded[:7]}..HEAD" in stderr


def test_relative_handoff_path_resolves_from_repo(tmp_path, monkeypatch):
    repo, recorded = _repo(tmp_path)
    _handoff(repo, recorded)
    _commit(repo, "second")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    code, _, _ = check_continue_freshness("continue.md", repo=repo)

    assert code == 2


def test_non_handoff_and_unknown_hash_fail_open(tmp_path):
    repo, _ = _repo(tmp_path)
    other = repo / "notes.md"
    other.write_text("notes", encoding="utf-8")
    handoff = _handoff(repo, "deadbeef")

    assert check_continue_freshness(str(other), repo=repo) == (0, "", "")
    assert check_continue_freshness(str(handoff), repo=repo) == (0, "", "")
