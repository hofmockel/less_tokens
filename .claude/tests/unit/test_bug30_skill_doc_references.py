"""Bug 30: bug-hunt SKILL.md had file coverage list and project path from AIPortfolio.

The high-yield file list and agent prompt template referenced the AIPortfolio
project, making them useless as guidance for less_tokens bug hunts.
"""
from __future__ import annotations

from pathlib import Path

from tests.conftest import REPO_ROOT

SKILL = REPO_ROOT / ".claude" / "skills" / "bug-hunt" / "SKILL.md"


def test_skill_md_does_not_reference_aiportfolio_path():
    """The agent prompt template must reference the less_tokens project, not AIPortfolio."""
    text = SKILL.read_text()
    assert "AIPortfolio" not in text, (
        "SKILL.md still references AIPortfolio project path — update to less_tokens (Bug 30)"
    )


def test_skill_md_coverage_list_references_less_tokens_files():
    """The high-yield file list must name actual less_tokens source files."""
    text = SKILL.read_text()
    # Key less_tokens files that should appear in the coverage list.
    assert "embeddings.py" in text
    assert "search.py" in text
    assert "search-first.py" in text
