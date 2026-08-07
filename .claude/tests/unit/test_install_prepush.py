"""Tests for the native pre-push continue.md-freshness hook (CN1)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from install import (
    _pre_push_script_rel,
    unwire_pre_push_hook,
    wire_pre_push_hook,
)


def _git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    return repo


def test_script_rel_prefers_claude_when_both(tmp_path):
    assert _pre_push_script_rel({"claude", "codex"}) == Path(
        ".claude/hooks/common/pre-push-continue-freshness.py"
    )


def test_script_rel_codex_only(tmp_path):
    assert _pre_push_script_rel({"codex"}) == Path(
        ".less_tokens/hooks/pre-push-continue-freshness.py"
    )


def test_wire_creates_hook_when_absent(tmp_path):
    repo = _git_repo(tmp_path)
    changed = wire_pre_push_hook({"claude"}, repo)
    hook = repo / ".git" / "hooks" / "pre-push"
    assert changed == 1
    assert hook.exists()
    if sys.platform != "win32":
        # NTFS has no POSIX execute bit, so os.chmod(0o755) is a no-op there
        # and st_mode never reflects it — Git for Windows runs hooks via its
        # bundled shell reading the shebang line, not the execute bit, so
        # this isn't something wire_pre_push_hook needs to fix; only the
        # assertion needs to be platform-aware.
        assert hook.stat().st_mode & 0o111  # executable
    assert "less_tokens (continue.md freshness)" in hook.read_text()
    assert ".claude/hooks/common/pre-push-continue-freshness.py" in hook.read_text()


def test_wire_is_idempotent(tmp_path):
    repo = _git_repo(tmp_path)
    wire_pre_push_hook({"claude"}, repo)
    changed = wire_pre_push_hook({"claude"}, repo)
    assert changed == 0


def test_wire_dry_run_does_not_write(tmp_path):
    repo = _git_repo(tmp_path)
    changed = wire_pre_push_hook({"claude"}, repo, dry_run=True)
    assert changed == 1
    assert not (repo / ".git" / "hooks" / "pre-push").exists()


def test_wire_composes_with_host_owned_hook(tmp_path):
    repo = _git_repo(tmp_path)
    hook = repo / ".git" / "hooks" / "pre-push"
    hook.write_text("#!/bin/sh\necho host-owned-check\n", encoding="utf-8")
    changed = wire_pre_push_hook({"claude"}, repo)
    text = hook.read_text()
    assert changed == 1
    assert "host-owned-check" in text
    assert "less_tokens (continue.md freshness)" in text
    assert text.index("host-owned-check") < text.index(
        "less_tokens (continue.md freshness)"
    )


def test_wire_updates_in_place_on_reinstall_with_changed_target(tmp_path):
    repo = _git_repo(tmp_path)
    wire_pre_push_hook({"claude"}, repo)
    # Simulate a fresh checkout at a different absolute path re-wiring —
    # the block content differs (path changed), so it must be replaced,
    # not duplicated.
    changed = wire_pre_push_hook({"codex"}, repo)
    text = (repo / ".git" / "hooks" / "pre-push").read_text()
    assert changed == 1
    assert text.count("less_tokens (continue.md freshness)") == 1
    assert ".less_tokens/hooks/pre-push-continue-freshness.py" in text


def test_unwire_removes_file_when_block_was_only_content(tmp_path):
    repo = _git_repo(tmp_path)
    wire_pre_push_hook({"claude"}, repo)
    unwire_pre_push_hook(repo, dry_run=False)
    assert not (repo / ".git" / "hooks" / "pre-push").exists()


def test_unwire_keeps_host_content(tmp_path):
    repo = _git_repo(tmp_path)
    hook = repo / ".git" / "hooks" / "pre-push"
    hook.write_text("#!/bin/sh\necho host-owned-check\n", encoding="utf-8")
    wire_pre_push_hook({"claude"}, repo)
    unwire_pre_push_hook(repo, dry_run=False)
    text = hook.read_text()
    assert "host-owned-check" in text
    assert "less_tokens (continue.md freshness)" not in text


def test_unwire_noop_when_absent(tmp_path):
    repo = _git_repo(tmp_path)
    assert unwire_pre_push_hook(repo, dry_run=False) == 0


def test_wire_noop_outside_git_repo(tmp_path):
    not_a_repo = tmp_path / "plain"
    not_a_repo.mkdir()
    assert wire_pre_push_hook({"claude"}, not_a_repo) == 0
