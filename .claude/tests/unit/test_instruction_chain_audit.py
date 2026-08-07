from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "tools"))
import instruction_chain_audit as m  # noqa: E402


def _home(tmp_path: Path) -> Path:
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    return home


def test_claude_chain_splits_fixed_vs_on_demand(tmp_path):
    base = tmp_path / "repo"
    (base / ".git").mkdir(parents=True)
    (base / "CLAUDE.md").write_text("# root\n" + "word " * 20, encoding="utf-8")

    rules = base / ".claude" / "rules"
    rules.mkdir(parents=True)
    (rules / "unscoped.md").write_text(
        "# Always\nGlobal convention.\n", encoding="utf-8"
    )
    (rules / "scoped.md").write_text(
        '---\nglobs: "src/**/*.ts"\n---\n# TS rules\nUse strict types.\n',
        encoding="utf-8",
    )

    home = _home(tmp_path)
    with patch.object(Path, "home", return_value=home):
        result = m.claude_chain(base, base)

    fixed_paths = {f["path"] for f in result["fixed"]}
    on_demand_paths = {f["path"] for f in result["on_demand"]}
    assert "CLAUDE.md" in fixed_paths
    assert ".claude/rules/unscoped.md" in fixed_paths
    assert ".claude/rules/scoped.md" in on_demand_paths
    assert result["fixed_tokens"] > 0
    assert result["on_demand_tokens"] > 0


def test_claude_chain_flags_disputed_paths_frontmatter(tmp_path):
    base = tmp_path / "repo"
    rules = base / ".claude" / "rules"
    rules.mkdir(parents=True)
    (base / ".git").mkdir()
    (rules / "risky.md").write_text(
        '---\npaths:\n  - "src/**/*.ts"\n---\n# Risky\nBody text.\n', encoding="utf-8"
    )

    home = _home(tmp_path)
    with patch.object(Path, "home", return_value=home):
        result = m.claude_chain(base, base)

    assert any("risky.md" in f and "17204" in f for f in result["flags"])


def test_claude_chain_flags_unscoped_path_specific_rule(tmp_path):
    base = tmp_path / "repo"
    rules = base / ".claude" / "rules"
    rules.mkdir(parents=True)
    (base / ".git").mkdir()
    body = "# Backend\nEdit files under /handlers/ ending in .py and .sql only.\n"
    (rules / "backend.md").write_text(body, encoding="utf-8")

    home = _home(tmp_path)
    with patch.object(Path, "home", return_value=home):
        result = m.claude_chain(base, base)

    assert any("backend.md" in f and "consider scoping" in f for f in result["flags"])


def test_claude_chain_nested_rules_dir_is_on_demand(tmp_path):
    base = tmp_path / "repo"
    (base / ".git").mkdir(parents=True)
    (base / "CLAUDE.md").write_text("# root\n", encoding="utf-8")
    nested_rules = base / "pkg" / ".claude" / "rules"
    nested_rules.mkdir(parents=True)
    (nested_rules / "pkg.md").write_text(
        "# Pkg rule\nAlways applies within pkg.\n", encoding="utf-8"
    )

    home = _home(tmp_path)
    with patch.object(Path, "home", return_value=home):
        result = m.claude_chain(base / "pkg", base)

    on_demand_paths = {f["path"] for f in result["on_demand"]}
    assert "pkg/.claude/rules/pkg.md" in on_demand_paths


def test_memory_summary_flags_over_limit(tmp_path):
    base = tmp_path / "repo"
    base.mkdir()
    home = tmp_path / "home"
    with patch.object(Path, "home", return_value=home):
        mem_dir = m._memory_dir_for(base)
        mem_dir.mkdir(parents=True)
        (mem_dir / "MEMORY.md").write_text(
            "\n".join(f"- entry {i}" for i in range(250)), encoding="utf-8"
        )
        (mem_dir / "topic.md").write_text("detail\n", encoding="utf-8")

        summary = m._memory_summary(base)

    assert summary["found"] is True
    assert summary["over_limit"] is True
    assert summary["topic_files"] == 1


def test_codex_chain_concatenates_root_down_with_override(tmp_path):
    base = tmp_path / "repo"
    (base / ".git").mkdir(parents=True)
    (base / ".codex").mkdir()
    (base / "AGENTS.md").write_text("root agents\n", encoding="utf-8")
    sub = base / "pkg"
    sub.mkdir()
    (sub / "AGENTS.override.md").write_text("pkg override\n", encoding="utf-8")
    (sub / "AGENTS.md").write_text("pkg agents (should be skipped)\n", encoding="utf-8")

    home = _home(tmp_path)
    with patch.object(Path, "home", return_value=home):
        result = m.codex_chain(sub, base)

    included_paths = [e["path"] for e in result["included"]]
    assert included_paths == ["AGENTS.md", "pkg/AGENTS.override.md"]


def test_codex_chain_stops_at_project_doc_max_bytes(tmp_path):
    base = tmp_path / "repo"
    (base / ".git").mkdir(parents=True)
    (base / "AGENTS.md").write_text("root " * 50, encoding="utf-8")
    sub = base / "pkg"
    sub.mkdir()
    (sub / "AGENTS.md").write_text("x" * 40000, encoding="utf-8")

    home = _home(tmp_path)
    with patch.object(Path, "home", return_value=home):
        result = m.codex_chain(sub, base)

    assert result["skipped_over_limit"]
    assert result["skipped_over_limit"][0]["path"] == "pkg/AGENTS.md"
    assert result["included_bytes"] < m.CODEX_DEFAULT_MAX_BYTES
