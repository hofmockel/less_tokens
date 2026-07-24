from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "tools"))
import claudemd_audit as audit_mod  # noqa: E402


REPO = Path(__file__).resolve().parent.parent.parent.parent
TOOL = REPO / ".claude" / "tools" / "claudemd_audit.py"


def _homes(topic="Widget spec", canonical="CANON.md", others=("OTHER.md",)):
    return [{"topic": topic, "canonical": canonical, "others": list(others)}]


def test_audit_docs_flags_missing_canonical(tmp_path):
    (tmp_path / "OTHER.md").write_text("# Other\n\n## Widget\nshort\n", encoding="utf-8")

    result = audit_mod.audit_docs(tmp_path, homes=_homes())

    assert len(result["violations"]) == 1
    v = result["violations"][0]
    assert v["kind"] == "missing-canonical"
    assert v["file"] == "OTHER.md"


def test_audit_docs_flags_over_length_section(tmp_path):
    (tmp_path / "CANON.md").write_text("# Canon\ncontent\n", encoding="utf-8")
    (tmp_path / "OTHER.md").write_text(
        "# Other\n\n## Widget\n" + ("word " * 100) + "\n", encoding="utf-8"
    )

    result = audit_mod.audit_docs(tmp_path, homes=_homes(), max_tokens=10)

    assert len(result["violations"]) == 1
    v = result["violations"][0]
    assert v["kind"] == "over-length"
    assert v["file"] == "OTHER.md"


def test_audit_docs_ok_when_pointer_is_short(tmp_path):
    (tmp_path / "CANON.md").write_text("# Canon\ncontent\n", encoding="utf-8")
    (tmp_path / "OTHER.md").write_text(
        "# Other\n\n## Widget\nSee CANON.md.\n", encoding="utf-8"
    )

    result = audit_mod.audit_docs(tmp_path, homes=_homes())

    assert result["violations"] == []


def test_audit_docs_ignores_non_matching_headings(tmp_path):
    (tmp_path / "CANON.md").write_text("# Canon\ncontent\n", encoding="utf-8")
    (tmp_path / "OTHER.md").write_text(
        "# Other\n\n## Unrelated\n" + ("word " * 100) + "\n", encoding="utf-8"
    )

    result = audit_mod.audit_docs(tmp_path, homes=_homes(), max_tokens=1)

    assert result["violations"] == []


def test_docs_cli_strict_passes_against_real_repo():
    result = subprocess.run(
        [sys.executable, str(TOOL), "--docs", "--strict", "--json"],
        cwd=REPO,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(REPO / ".claude" / "tools")},
        timeout=10,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["violations"] == []
