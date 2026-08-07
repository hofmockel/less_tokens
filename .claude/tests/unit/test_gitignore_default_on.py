"""Installer adds the managed .gitignore block by default.

Generated artifacts (index.db, .claude/state/) silently pollute the host
git repo otherwise. Default-on with --no-gitignore opt-out keeps a fresh
install's `git status` clean without forcing the user to remember a flag.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
import install  # noqa: E402


def _git_repo(tmp_path: Path) -> Path:
    (tmp_path / ".git").mkdir()
    return tmp_path


def test_handle_gitignore_writes_block_when_want_true(tmp_path):
    root = _git_repo(tmp_path)
    changes = install.handle_gitignore(root, want=True, dry_run=False)
    assert changes == 1
    gi = (root / ".gitignore").read_text()
    assert "less_tokens managed block" in gi or "less_tokens" in gi
    assert "index.db" in gi


def test_handle_gitignore_skips_when_want_false(tmp_path):
    root = _git_repo(tmp_path)
    changes = install.handle_gitignore(root, want=False, dry_run=False)
    assert changes == 0
    assert not (root / ".gitignore").exists()


def test_no_gitignore_flag_is_parseable():
    """The arg parser exposes --no-gitignore (default behavior is on)."""
    src = (REPO / "install.py").read_text()
    assert "--no-gitignore" in src, "expose an opt-out flag, not just --gitignore"


def test_gitignore_default_resolves_true_in_main():
    """In main(), the call site passes True unless the user opted out.

    Source-level check: handle_gitignore receives a value derived from
    `not args.no_gitignore` (or equivalent), not the bare `args.gitignore`.
    """
    src = (REPO / "install.py").read_text()
    # The call site must reflect the inverted default.
    assert "args.no_gitignore" in src or "not args.no_gitignore" in src
