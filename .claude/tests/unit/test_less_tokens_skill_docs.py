"""Tests for the generated Claude/Codex less-tokens skill manuals."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location(
    "less_tokens_skill_docs",
    REPO / ".claude" / "tools" / "less_tokens_skill_docs.py",
)
assert SPEC and SPEC.loader
docs = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = docs
SPEC.loader.exec_module(docs)


def test_generated_skills_match_checked_in_outputs():
    for agent, overlay in docs.OVERLAYS.items():
        assert docs.render(agent) == overlay.target.read_text(encoding="utf-8")


def test_render_is_byte_stable():
    for agent in docs.OVERLAYS:
        assert docs.render(agent) == docs.render(agent)


def test_template_uses_only_declared_platform_variables():
    template = docs.TEMPLATE.read_text(encoding="utf-8")
    placeholders = set(re.findall(r"\$([a-z_]+)", template))
    assert placeholders == {
        "audit_command",
        "command_prefix",
        "delegation",
        "description",
        "digest_constraints",
        "instruction_doc",
        "reminder_hook",
        "runtime_path",
        "state_path",
    }


def test_platform_mechanics_remain_explicit():
    claude = docs.render("claude")
    codex = docs.render("codex")
    assert ".claude/.venv-tokens/bin/python .claude/tools/search.py" in claude
    assert ".less_tokens/bin/python .less_tokens/tools/search.py" in codex
    assert "Use the Agent tool" in claude
    assert "fork_context=false" in codex
    assert "caveman-reminder.py" in claude
    assert "terse-reminder.py" in codex


def test_check_passes_for_checked_in_skills():
    assert docs.update_skills(check=True) == 0
