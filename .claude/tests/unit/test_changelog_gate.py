"""Unit tests for tools/changelog_gate.py — backlog-lifecycle gate."""
from __future__ import annotations

from tools.changelog_gate import backlog_ids, check, cited_ids, unreleased_section

CHANGELOG = """# Changelog

## [Unreleased]

### Fixed
- [P1] Delete hook-duplicating prose from CLAUDE.md
- plain entry with no id

## [1.0.0]
- [F9] released long ago, should be ignored
"""

BACKLOG = """# Backlog

- **P1 — Delete hook-duplicating prose** *(fixed)* — still here.
- **F2 — Doc dedup** *(fixed)* — unrelated.
"""


def write(root, changelog=CHANGELOG, backlog=BACKLOG):
    (root / "CHANGELOG.md").write_text(changelog)
    (root / "BACKLOG.md").write_text(backlog)


class TestParsing:
    def test_unreleased_excludes_released(self):
        section = unreleased_section(CHANGELOG)
        assert "P1" in section
        assert "F9" not in section  # below the next ## heading

    def test_cited_ids_only_unreleased(self):
        assert cited_ids(CHANGELOG) == {"P1"}

    def test_backlog_ids(self):
        assert backlog_ids(BACKLOG) == {"P1", "F2"}


class TestCheck:
    def test_fails_when_shipped_id_lingers(self, tmp_path):
        write(tmp_path)
        assert check(tmp_path) == 1  # P1 cited but still in backlog

    def test_passes_when_deleted(self, tmp_path):
        write(tmp_path, backlog="# Backlog\n- **F2 — Doc dedup** *(fixed)*\n")
        assert check(tmp_path) == 0

    def test_passes_with_no_citations(self, tmp_path):
        write(tmp_path, changelog="# Changelog\n\n## [Unreleased]\n- plain\n")
        assert check(tmp_path) == 0

    def test_missing_file_returns_2(self, tmp_path):
        (tmp_path / "CHANGELOG.md").write_text(CHANGELOG)
        assert check(tmp_path) == 2  # no BACKLOG.md
