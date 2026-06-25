"""Tests for shared hook manifest and parity matrix."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(REPO))

from agents.common.hooks.hook_manifest import HOOK_SPECS
from install import build_claude_hook_entries, build_codex_hook_entries


def _args(**kwargs) -> argparse.Namespace:
    defaults = {"truncate": True, "compact": True, "caveman": True}
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def test_manifest_has_one_spec_per_hook_name():
    names = [spec.name for spec in HOOK_SPECS]
    assert len(names) == len(set(names))


def test_parity_matrix_matches_manifest():
    parity = json.loads((REPO / "agents" / "common" / "hooks" / "parity.json").read_text())
    manifest_names = {spec.name for spec in HOOK_SPECS}
    assert set(parity) == manifest_names
    for spec in HOOK_SPECS:
        assert parity[spec.name]["claude"] == ("shipped" if spec.claude else "missing")
        assert parity[spec.name]["codex"] == ("shipped" if spec.codex else "missing")
        if spec.optional_flag:
            assert parity[spec.name].get("optional") is True


def test_emitters_are_generated_from_manifest(tmp_path):
    args = _args()
    claude = build_claude_hook_entries(tmp_path / ".venv" / "bin" / "python", tmp_path, args)
    codex = build_codex_hook_entries(tmp_path / ".venv" / "bin" / "python", tmp_path, args)
    expected_claude = sum(len(spec.claude) for spec in HOOK_SPECS)
    expected_codex = sum(len(spec.codex) for spec in HOOK_SPECS)
    assert len(claude) == expected_claude
    assert len(codex) == expected_codex
    assert any("caveman-reminder.py" in cmd for _, _, cmd in claude)
    assert any("terse-reminder.py" in cmd for _, _, cmd in codex)
