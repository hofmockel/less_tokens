"""Tests for caveman CLAUDE.md append/remove in install.py."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from install import (
    _CM_END,
    _CM_START,
    _caveman_in_claude_md,
    _remove_caveman_block,
    handle_caveman_claude_md,
)


# ---------------------------------------------------------------------------
# _caveman_in_claude_md
# ---------------------------------------------------------------------------

class TestCavemanInClaudeMd:
    def test_returns_false_when_file_missing(self, tmp_path):
        assert _caveman_in_claude_md(tmp_path) is False

    def test_detects_block_marker(self, tmp_path):
        (tmp_path / "CLAUDE.md").write_text(f"{_CM_START}\nsome text\n{_CM_END}\n")
        assert _caveman_in_claude_md(tmp_path) is True

    def test_detects_legacy_caveman_mode_string(self, tmp_path):
        (tmp_path / "CLAUDE.md").write_text("## Output Style — Caveman Mode\n")
        assert _caveman_in_claude_md(tmp_path) is True

    def test_returns_false_when_neither_present(self, tmp_path):
        (tmp_path / "CLAUDE.md").write_text("# CLAUDE.md\nsome content\n")
        assert _caveman_in_claude_md(tmp_path) is False


# ---------------------------------------------------------------------------
# handle_caveman_claude_md
# ---------------------------------------------------------------------------

class TestHandleCavemanClaudeMd:
    def test_creates_claude_md_with_header_when_absent(self, tmp_path):
        result = handle_caveman_claude_md(tmp_path, dry_run=False)
        assert result == 1
        text = (tmp_path / "CLAUDE.md").read_text()
        assert text.startswith("# CLAUDE.md")
        assert _CM_START in text
        assert _CM_END in text

    def test_appends_to_existing_claude_md(self, tmp_path):
        (tmp_path / "CLAUDE.md").write_text("# CLAUDE.md\nexisting content\n")
        result = handle_caveman_claude_md(tmp_path, dry_run=False)
        assert result == 1
        text = (tmp_path / "CLAUDE.md").read_text()
        assert "existing content" in text
        assert _CM_START in text

    def test_idempotent_when_block_already_present(self, tmp_path):
        (tmp_path / "CLAUDE.md").write_text(
            f"# CLAUDE.md\n{_CM_START}\ncaveman\n{_CM_END}\n"
        )
        result = handle_caveman_claude_md(tmp_path, dry_run=False)
        assert result == 0
        # File unchanged — block not duplicated
        text = (tmp_path / "CLAUDE.md").read_text()
        assert text.count(_CM_START) == 1

    def test_idempotent_with_legacy_caveman_mode(self, tmp_path):
        (tmp_path / "CLAUDE.md").write_text("## Output Style — Caveman Mode\n")
        result = handle_caveman_claude_md(tmp_path, dry_run=False)
        assert result == 0

    def test_dry_run_does_not_write(self, tmp_path):
        result = handle_caveman_claude_md(tmp_path, dry_run=True)
        assert result == 1
        assert not (tmp_path / "CLAUDE.md").exists()

    def test_dry_run_no_write_when_existing(self, tmp_path):
        original = "# CLAUDE.md\nexisting\n"
        (tmp_path / "CLAUDE.md").write_text(original)
        handle_caveman_claude_md(tmp_path, dry_run=True)
        assert (tmp_path / "CLAUDE.md").read_text() == original

    def test_block_contains_caveman_content(self, tmp_path):
        handle_caveman_claude_md(tmp_path, dry_run=False)
        text = (tmp_path / "CLAUDE.md").read_text()
        # caveman.md content should appear between markers
        start_idx = text.index(_CM_START)
        end_idx = text.index(_CM_END)
        block = text[start_idx:end_idx]
        assert "Caveman Mode" in block or "caveman" in block.lower()

    def test_missing_caveman_src_is_noop(self, tmp_path, monkeypatch):
        import install
        monkeypatch.setattr(install, "SOURCE", tmp_path / "nosrc")
        result = handle_caveman_claude_md(tmp_path, dry_run=False)
        assert result == 0
        assert not (tmp_path / "CLAUDE.md").exists()

    def test_existing_file_without_trailing_newline(self, tmp_path):
        (tmp_path / "CLAUDE.md").write_text("# CLAUDE.md\ncontent")
        handle_caveman_claude_md(tmp_path, dry_run=False)
        text = (tmp_path / "CLAUDE.md").read_text()
        assert "content" in text
        assert _CM_START in text


# ---------------------------------------------------------------------------
# _remove_caveman_block
# ---------------------------------------------------------------------------

class TestRemoveCavemanBlock:
    def test_noop_when_file_missing(self, tmp_path):
        assert _remove_caveman_block(tmp_path / "CLAUDE.md", dry_run=False) is False

    def test_noop_when_no_block(self, tmp_path):
        p = tmp_path / "CLAUDE.md"
        p.write_text("# CLAUDE.md\nsome content\n")
        assert _remove_caveman_block(p, dry_run=False) is False
        assert p.read_text() == "# CLAUDE.md\nsome content\n"

    def test_removes_block(self, tmp_path):
        p = tmp_path / "CLAUDE.md"
        p.write_text(f"# CLAUDE.md\n\n{_CM_START}\ncaveman\n{_CM_END}\n")
        assert _remove_caveman_block(p, dry_run=False) is True
        text = p.read_text()
        assert _CM_START not in text
        assert _CM_END not in text
        assert "# CLAUDE.md" in text

    def test_dry_run_does_not_modify(self, tmp_path):
        p = tmp_path / "CLAUDE.md"
        original = f"# CLAUDE.md\n{_CM_START}\ncaveman\n{_CM_END}\n"
        p.write_text(original)
        _remove_caveman_block(p, dry_run=True)
        assert p.read_text() == original

    def test_deletes_file_when_only_block_remains(self, tmp_path):
        p = tmp_path / "CLAUDE.md"
        p.write_text(f"{_CM_START}\ncaveman\n{_CM_END}\n")
        _remove_caveman_block(p, dry_run=False)
        assert not p.exists()

    def test_roundtrip_append_then_remove(self, tmp_path):
        original = "# CLAUDE.md\nexisting content\n"
        (tmp_path / "CLAUDE.md").write_text(original)
        handle_caveman_claude_md(tmp_path, dry_run=False)
        _remove_caveman_block(tmp_path / "CLAUDE.md", dry_run=False)
        assert (tmp_path / "CLAUDE.md").read_text() == original
