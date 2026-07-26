"""Regression test for PT8: subagent-metrics and subagent-guidance are real,
manifest-registered Codex adapters (agents/common/hooks/hook_manifest.py), so
this repo's own dogfood .codex/hooks/ must carry both installed scripts and
.codex/hooks.json must wire every HookWire the manifest declares for them."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def codex_hooks_json(repo_root: Path) -> dict:
    return json.loads((repo_root / ".codex" / "hooks.json").read_text(encoding="utf-8"))


def _commands(codex_hooks_json: dict) -> list[str]:
    return [
        hook.get("command", "")
        for group in codex_hooks_json.get("hooks", {}).values()
        for entry in group
        for hook in entry.get("hooks", [])
    ]


def test_subagent_guidance_script_installed(repo_root: Path):
    assert (repo_root / ".codex" / "hooks" / "subagent-guidance.py").exists()


def test_subagent_metrics_script_installed(repo_root: Path):
    assert (repo_root / ".codex" / "hooks" / "subagent-metrics.py").exists()


def test_subagent_guidance_wired_in_hooks_json(codex_hooks_json: dict):
    commands = _commands(codex_hooks_json)
    assert any("subagent-guidance.py" in c for c in commands)


def test_subagent_metrics_wired_in_hooks_json(codex_hooks_json: dict):
    commands = _commands(codex_hooks_json)
    matching = [c for c in commands if "subagent-metrics.py" in c]
    # Manifest wires subagent-metrics on 4 distinct events (CX29/CX18):
    # PreToolUse ^Agent$, PostToolUse ^Agent$, SubagentStart, SubagentStop.
    assert len(matching) == 4
