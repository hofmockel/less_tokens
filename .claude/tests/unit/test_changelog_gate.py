"""Unit tests for tools/changelog_gate.py — backlog/changelog lifecycle gate.

Two rules: (1) changelog-exists for code changes, (2) backlog cross-check that a
CHANGELOG-cited ID is gone from BACKLOG.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]

_spec = importlib.util.spec_from_file_location(
    "changelog_gate", REPO / ".claude" / "tools" / "changelog_gate.py"
)
gate = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(gate)

CL_WITH = "## [Unreleased]\n\n### Fixed\n- **thing** — fixed it.\n\n## [1.0.0]\n- old\n"
CL_EMPTY = "## [Unreleased]\n\n## [1.0.0]\n- old\n"


# --- Rule 1: changelog-exists ------------------------------------------------


def test_is_code_change():
    assert gate.is_code_change(".claude/tools/search.py")
    assert gate.is_code_change("agents/common/hooks/x.py")
    assert not gate.is_code_change(".claude/tests/unit/test_x.py")
    assert not gate.is_code_change("CLAUDE.md")
    assert not gate.is_code_change("README.md")
    # Windows separators normalize
    assert gate.is_code_change(".claude\\tools\\search.py")


def test_unreleased_entries_parsing():
    assert gate.unreleased_entries(CL_WITH) == ["- **thing** — fixed it."]
    assert gate.unreleased_entries(CL_EMPTY) == []
    # old-release bullets are not counted
    assert "- old" not in gate.unreleased_entries(CL_WITH)


def test_docs_only_change_skips_gate():
    ok, msg = gate.check(["CLAUDE.md", "README.md"], CL_EMPTY)
    assert ok, msg


def test_tests_only_change_skips_gate():
    ok, _ = gate.check([".claude/tests/unit/test_foo.py"], CL_EMPTY)
    assert ok


def test_code_change_without_changelog_fails():
    ok, msg = gate.check([".claude/tools/search.py"], CL_WITH)
    assert not ok
    assert "not in the diff" in msg


def test_code_change_with_empty_unreleased_fails():
    ok, msg = gate.check([".claude/tools/search.py", "CHANGELOG.md"], CL_EMPTY)
    assert not ok
    assert "no entries" in msg


def test_code_change_documented_passes():
    ok, msg = gate.check([".claude/tools/search.py", "CHANGELOG.md"], CL_WITH)
    assert ok, msg


# --- Rule 2: backlog cross-check ---------------------------------------------

CL_CITES_P1 = (
    "## [Unreleased]\n- [P1] shipped it\n- plain entry\n\n## [1.0.0]\n- [F9] old\n"
)
BACKLOG = "# Backlog\n- **P1 — thing** *(fixed)*\n- **F2 — other** *(fixed)*\n"


def test_cited_ids_only_unreleased():
    assert gate.cited_ids(CL_CITES_P1) == {"P1"}  # F9 below next heading ignored


def test_backlog_ids():
    assert gate.backlog_ids(BACKLOG) == {"P1", "F2"}


def test_lingering_when_shipped_id_remains():
    assert gate.lingering_backlog_ids(CL_CITES_P1, BACKLOG) == ["P1"]


def test_no_lingering_when_deleted():
    deleted = "# Backlog\n- **F2 — other** *(fixed)*\n"
    assert gate.lingering_backlog_ids(CL_CITES_P1, deleted) == []


def test_no_lingering_without_citations():
    assert gate.lingering_backlog_ids(CL_WITH, BACKLOG) == []
