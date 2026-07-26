"""Regression test for PT2: truncate-output has no Codex adapter in the manifest
(agents/common/hooks/hook_manifest.py, CX28), so this repo's own dogfood
.codex/hooks.json must carry no wiring for it and .codex/hooks/truncate-output.py
must not exist as an installed copy."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def codex_hooks_json(repo_root: Path) -> dict:
    return json.loads((repo_root / ".codex" / "hooks.json").read_text(encoding="utf-8"))


def test_no_truncate_output_script_installed(repo_root: Path):
    assert not (repo_root / ".codex" / "hooks" / "truncate-output.py").exists()


def test_no_truncate_output_wiring_in_hooks_json(codex_hooks_json: dict):
    commands = [
        hook.get("command", "")
        for group in codex_hooks_json.get("hooks", {}).values()
        for entry in group
        for hook in entry.get("hooks", [])
    ]
    assert not any("truncate-output.py" in command for command in commands)
