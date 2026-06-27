"""Tests for handle_agents_md() — idempotent AGENTS.md fragment management."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(REPO))
from install import handle_agents_md

FRAGMENT = REPO / "agents" / "codex" / "instructions" / "AGENTS.md.fragment"
_BEGIN = "<!-- less_tokens: begin -->"
_END = "<!-- less_tokens: end -->"


class TestHandleAgentsMd:
    def test_creates_agents_md_when_absent(self, tmp_path):
        result = handle_agents_md(FRAGMENT, tmp_path)
        assert result == 0
        content = (tmp_path / "AGENTS.md").read_text()
        assert _BEGIN in content
        assert _END in content

    def test_fragment_content_included(self, tmp_path):
        handle_agents_md(FRAGMENT, tmp_path)
        content = (tmp_path / "AGENTS.md").read_text()
        assert "Token Discipline" in content
        assert "less-tokens" in content

    def test_appends_to_existing_file_preserving_content(self, tmp_path):
        agents_md = tmp_path / "AGENTS.md"
        agents_md.write_text("# My Project Rules\n\nDo not break production.\n")
        handle_agents_md(FRAGMENT, tmp_path)
        content = agents_md.read_text()
        assert "# My Project Rules" in content
        assert "Do not break production" in content
        assert _BEGIN in content

    def test_idempotent_on_second_call(self, tmp_path):
        handle_agents_md(FRAGMENT, tmp_path)
        first = (tmp_path / "AGENTS.md").read_text()
        result = handle_agents_md(FRAGMENT, tmp_path)
        assert result == 0
        assert (tmp_path / "AGENTS.md").read_text() == first

    def test_updates_stale_block_in_place(self, tmp_path):
        agents_md = tmp_path / "AGENTS.md"
        agents_md.write_text(
            "# Rules\n\n"
            f"{_BEGIN}\nSTALE CONTENT HERE\n{_END}\n"
        )
        handle_agents_md(FRAGMENT, tmp_path)
        content = agents_md.read_text()
        assert "STALE CONTENT HERE" not in content
        assert "# Rules" in content
        assert _BEGIN in content

    def test_updated_block_contains_current_fragment(self, tmp_path):
        agents_md = tmp_path / "AGENTS.md"
        agents_md.write_text(f"{_BEGIN}\nOLD\n{_END}\n")
        handle_agents_md(FRAGMENT, tmp_path)
        assert "Token Discipline" in agents_md.read_text()

    def test_fixed_context_points_to_skill_not_command_examples(self, tmp_path):
        handle_agents_md(FRAGMENT, tmp_path)
        content = (tmp_path / "AGENTS.md").read_text()
        assert "use the `less-tokens` skill" in content
        assert ".less_tokens/bin/python" not in content

    def test_dry_run_does_not_create_file(self, tmp_path):
        handle_agents_md(FRAGMENT, tmp_path, dry_run=True)
        assert not (tmp_path / "AGENTS.md").exists()

    def test_dry_run_does_not_modify_existing_file(self, tmp_path):
        agents_md = tmp_path / "AGENTS.md"
        agents_md.write_text("# Original\n")
        handle_agents_md(FRAGMENT, tmp_path, dry_run=True)
        assert agents_md.read_text() == "# Original\n"

    def test_missing_fragment_returns_one(self, tmp_path):
        result = handle_agents_md(tmp_path / "nonexistent_fragment.md", tmp_path)
        assert result == 1
