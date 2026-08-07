"""Bug: lean-ls crashes on broken symlinks.

Broken symlink returns is_file()=False and is added to `dirs`; subsequent
iterdir() raises FileNotFoundError which is not caught (only PermissionError is).

Fix: use is_dir() instead of `not is_file()` so broken symlinks are neither
files nor dirs and are simply skipped.
"""

from __future__ import annotations

from tests.conftest import REPO_ROOT, load_hook


def test_broken_symlink_does_not_crash(tmp_path):
    """lean-ls must not crash when a directory contains a broken symlink."""
    mod = load_hook(REPO_ROOT / ".claude" / "tools" / "lean-ls.py")

    # Create a broken symlink in tmp_path
    broken = tmp_path / "dangling_link"
    broken.symlink_to(tmp_path / "nonexistent_target")
    assert broken.is_symlink()
    assert not broken.exists()  # confirms it's broken

    # Also add a real file so there's something to list
    (tmp_path / "real_file.txt").write_text("hello")

    lines: list[str] = []
    mod._walk(tmp_path, 0, 2, 20, set(), lines, "")

    assert any("real_file.txt" in ln for ln in lines), "real file must still be listed"
    # Broken symlink should be silently skipped, not cause a crash or appear as a dir
    assert not any("dangling_link/" in ln for ln in lines), (
        "broken symlink must not appear as a directory"
    )
