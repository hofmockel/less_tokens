"""Tests for the Codex agentsmd skill."""
from __future__ import annotations

from pathlib import Path


REPO = Path(__file__).parent.parent.parent.parent
SKILL = REPO / "agents" / "codex" / "skills" / "agentsmd" / "SKILL.md"


def test_agentsmd_skill_exists():
    assert SKILL.exists()


def test_agentsmd_skill_points_to_codex_audit_tool():
    text = SKILL.read_text(encoding="utf-8")
    assert "name: agentsmd" in text
    assert ".less_tokens/tools/agentsmd_audit.py" in text
    assert "AGENTS_MD_TOKEN_BUDGET" in text


def test_less_tokens_skill_carries_command_examples():
    skill = REPO / "agents" / "codex" / "skills" / "less-tokens" / "SKILL.md"
    text = skill.read_text(encoding="utf-8")
    assert ".less_tokens/bin/python .less_tokens/tools/search.py" in text
    assert ".less_tokens/bin/python .less_tokens/tools/symbols.py" in text
    assert ".less_tokens/bin/python .less_tokens/tools/read_guard.py" in text
    assert ".less_tokens/bin/python .less_tokens/tools/agentsmd_audit.py" in text
