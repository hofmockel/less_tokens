"""Bug 27: REPO resolution in hooks was broken in the dev environment.

In older versions, _resolve_repo() only checked for .git when walking up the
directory tree.  In the dev environment (working inside the less_tokens repo
itself), a clone without an initialized .git would silently fall through to
the wrong path.  The fix also checks for CLAUDE.md so non-git workspaces
(CI clones, zip extracts) resolve correctly.

Additionally, the LESS_TOKENS_REPO env var override must take precedence over
the auto-detection walk.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from tests.conftest import REPO_ROOT, load_hook


def test_resolve_repo_uses_env_var(tmp_path, monkeypatch):
    """LESS_TOKENS_REPO env var must override the auto-detect walk."""
    monkeypatch.setenv("LESS_TOKENS_REPO", str(tmp_path))
    mod = load_hook(REPO_ROOT / ".claude" / "hooks" / "search-first.py")
    assert mod._resolve_repo() == tmp_path.resolve()


def test_resolve_repo_finds_claude_md_without_git(tmp_path, monkeypatch):
    """A CLAUDE.md without .git must still resolve the project root."""
    monkeypatch.delenv("LESS_TOKENS_REPO", raising=False)
    # Create a fake project with CLAUDE.md but no .git
    project = tmp_path / "myproject"
    project.mkdir()
    (project / "CLAUDE.md").write_text("# project")
    hooks_dir = project / ".claude" / "hooks"
    hooks_dir.mkdir(parents=True)
    hook_file = hooks_dir / "search-first.py"
    real_hook = (REPO_ROOT / ".claude" / "hooks" / "search-first.py").read_text()
    hook_file.write_text(real_hook)

    import importlib.util
    spec = importlib.util.spec_from_file_location("sf_test", hook_file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    assert mod.REPO == project


def test_resolve_repo_finds_git_without_claude_md(tmp_path, monkeypatch):
    """A .git without CLAUDE.md must also resolve the project root."""
    monkeypatch.delenv("LESS_TOKENS_REPO", raising=False)
    project = tmp_path / "gitproject"
    project.mkdir()
    (project / ".git").mkdir()
    hooks_dir = project / ".claude" / "hooks"
    hooks_dir.mkdir(parents=True)
    hook_file = hooks_dir / "search-first.py"
    real_hook = (REPO_ROOT / ".claude" / "hooks" / "search-first.py").read_text()
    hook_file.write_text(real_hook)

    import importlib.util
    spec = importlib.util.spec_from_file_location("sf_test2", hook_file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    assert mod.REPO == project
