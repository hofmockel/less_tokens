"""Tests for the Claude-side less-tokens skill and narrow agent definitions (G14/G16/G17)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(REPO))
from install import _install_specs

SKILL_SRC = REPO / "agents" / "claude" / "skills" / "less-tokens" / "SKILL.md"
AGENTS_SRC = REPO / "agents" / "claude" / "agents"


def _frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    end = text.index("\n---", 4)
    return yaml.safe_load(text[4:end])


class TestInstallSpecsIncludeClaudeSkillAndAgents:
    def test_specs_include_less_tokens_skill(self):
        specs = _install_specs(caveman=False, agents={"claude"})
        dest_dirs = [s[1] for s in specs]
        assert ".claude/skills/less-tokens" in dest_dirs

    def test_specs_include_agents_dir(self):
        specs = _install_specs(caveman=False, agents={"claude"})
        dest_dirs = [s[1] for s in specs]
        assert ".claude/agents" in dest_dirs

    def test_codex_only_install_excludes_claude_skill(self):
        specs = _install_specs(caveman=False, agents={"codex"})
        dest_dirs = [s[1] for s in specs]
        assert ".claude/skills/less-tokens" not in dest_dirs
        assert ".claude/agents" not in dest_dirs


class TestSkillContent:
    def test_skill_frontmatter(self):
        fm = _frontmatter(SKILL_SRC)
        assert fm["name"] == "less-tokens"
        assert "spawn" in fm["description"] or "subagent" in fm["description"]

    def test_skill_references_narrow_agents(self):
        text = SKILL_SRC.read_text(encoding="utf-8")
        assert ".claude/agents/explorer.md" in text
        assert ".claude/agents/verifier.md" in text


class TestNarrowAgentDefinitions:
    @pytest.mark.parametrize(
        "name,allowed_tools",
        [
            ("explorer.md", {"Read", "Grep", "Glob"}),
            ("verifier.md", {"Bash", "Read"}),
        ],
    )
    def test_agent_tools_allowlist_is_narrow(self, name, allowed_tools):
        fm = _frontmatter(AGENTS_SRC / name)
        tools = {t.strip() for t in fm["tools"].split(",")}
        assert tools == allowed_tools

    def test_agent_definitions_have_required_frontmatter(self):
        for path in sorted(AGENTS_SRC.glob("*.md")):
            fm = _frontmatter(path)
            assert fm.get("name")
            assert fm.get("description")
            assert fm.get("tools")

    def test_explorer_cannot_edit_or_run_commands(self):
        fm = _frontmatter(AGENTS_SRC / "explorer.md")
        tools = {t.strip() for t in fm["tools"].split(",")}
        assert not tools & {"Edit", "Write", "Bash"}

    def test_verifier_cannot_edit(self):
        fm = _frontmatter(AGENTS_SRC / "verifier.md")
        tools = {t.strip() for t in fm["tools"].split(",")}
        assert not tools & {"Edit", "Write"}
