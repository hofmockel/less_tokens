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


def _skill(root: Path, name: str, description: str | None) -> None:
    d = root / name
    d.mkdir(parents=True)
    if description is None:
        (d / "SKILL.md").write_text(f"# {name}\nno frontmatter here\n", encoding="utf-8")
    else:
        (d / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: {description}\n---\n# {name}\nbody\n",
            encoding="utf-8",
        )


def test_parse_skill_desc_handles_folded_scalar(tmp_path):
    d = tmp_path / "folded"
    d.mkdir()
    (d / "SKILL.md").write_text(
        "---\nname: folded\ndescription: >-\n  one two three\n  four five\n---\nbody\n",
        encoding="utf-8",
    )
    item = audit_mod.parse_skill_desc(d / "SKILL.md")
    assert item["name"] == "folded"
    assert item["description"] == "one two three four five"


def test_parse_skill_desc_missing_frontmatter(tmp_path):
    d = tmp_path / "redirect"
    d.mkdir()
    (d / "SKILL.md").write_text("# Redirect\nsee other file\n", encoding="utf-8")
    item = audit_mod.parse_skill_desc(d / "SKILL.md")
    assert item["name"] == "redirect"
    assert item["description"] == ""


def test_audit_skills_flags_over_cap_and_missing(tmp_path):
    skills = tmp_path / ".claude" / "skills"
    _skill(skills, "tiny", "short two")
    _skill(skills, "big", "word " * 30)
    _skill(skills, "nodesc", None)

    # Avoid network/model dependency: force the overlap check to no-op.
    with patch.object(audit_mod, "BASE", tmp_path), \
         patch.object(audit_mod, "desc_overlap", return_value=None):
        result = audit_mod.audit_skills(skills, word_cap=10, dup_sim=0.85)

    by_name = {r["name"]: r for r in result["skills"]}
    assert by_name["big"]["over_cap"] is True
    assert by_name["tiny"]["over_cap"] is False
    assert by_name["nodesc"]["missing"] is True
    assert "NO-DESC" in by_name["nodesc"]["verdict"]
    assert result["over_cap"] is True
    assert result["missing"] is True
    assert result["dup_check"] is False


def test_skill_verdict_overlap_takes_priority():
    v = audit_mod.skill_verdict(5, cap=10, dup_for=(0.92, "other"), dup_sim=0.85)
    assert v.startswith("OVERLAP") and "other" in v


def test_skills_cli_json_uses_default_word_cap(tmp_path):
    skills = tmp_path / ".claude" / "skills"
    _skill(skills, "alpha", "alpha does a thing")

    result = subprocess.run(
        [sys.executable, str(TOOL), "--skills", "--skills-dir", str(skills), "--json"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(REPO / ".claude" / "tools")},
        timeout=30,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["word_cap"] == audit_mod.SKILL_DESC_WORD_CAP
    assert payload["skills"][0]["name"] == "alpha"


def test_skills_cli_strict_fails_on_missing_description(tmp_path):
    skills = tmp_path / ".claude" / "skills"
    _skill(skills, "broken", None)

    result = subprocess.run(
        [sys.executable, str(TOOL), "--skills", "--skills-dir", str(skills), "--strict"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(REPO / ".claude" / "tools")},
        timeout=30,
    )

    assert result.returncode == 1
    assert "NO-DESC" in result.stdout
