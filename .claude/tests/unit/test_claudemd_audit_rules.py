from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "tools"))
import claudemd_audit as audit_mod  # noqa: E402


REPO = Path(__file__).resolve().parent.parent.parent.parent
TOOL = REPO / ".claude" / "tools" / "claudemd_audit.py"


def test_audit_rules_reports_each_markdown_rule(tmp_path):
    rules = tmp_path / ".claude" / "rules"
    rules.mkdir(parents=True)
    (rules / "short.md").write_text("# Short\nKeep this.\n", encoding="utf-8")
    (rules / "long.md").write_text("# Long\n" + ("word " * 200), encoding="utf-8")
    (rules / "ignore.txt").write_text("not markdown\n", encoding="utf-8")

    with patch.object(audit_mod, "BASE", tmp_path):
        result = audit_mod.audit_rules(rules, budget=50)

    assert result["path"] == ".claude/rules"
    assert [Path(item["path"]).name for item in result["files"]] == ["long.md", "short.md"]
    assert result["over_budget"] is True
    assert result["total_tokens"] > 0


def test_rules_cli_json_uses_rules_default_budget(tmp_path):
    rules = tmp_path / ".claude" / "rules"
    rules.mkdir(parents=True)
    (rules / "rule.md").write_text("# Rule\nshort\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(TOOL), "--rules", "--rules-dir", str(rules), "--json"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(REPO / ".claude" / "tools")},
        timeout=10,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["budget"] == audit_mod.RULES_TOKEN_BUDGET
    assert payload["files"][0]["path"].endswith("rule.md")


def test_rules_cli_strict_fails_when_rule_exceeds_budget(tmp_path):
    rules = tmp_path / ".claude" / "rules"
    rules.mkdir(parents=True)
    (rules / "big.md").write_text("# Big\n" + ("token " * 80), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(TOOL), "--rules", "--rules-dir", str(rules), "--budget", "5", "--strict"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(REPO / ".claude" / "tools")},
        timeout=10,
    )

    assert result.returncode == 1
    assert ".claude/rules" in result.stdout or str(rules) in result.stdout
