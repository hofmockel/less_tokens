"""P2: changelog merge gate — pure-check unit tests."""
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
