"""Tests for shared hook manifest and parity matrix."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(REPO))

from agents.common.hooks.hook_manifest import (
    CODEX_HOOK_CONTRACT_RANGE,
    HOOK_SPECS,
    codex_hook_contract_supports,
    codex_hooks_json_value,
    codex_hooks_schema,
    flatten_codex_hooks,
    parse_codex_version,
)
from install import build_claude_hook_entries, build_codex_hook_entries

_DOCS_SPEC = importlib.util.spec_from_file_location(
    "hook_parity_docs",
    REPO / ".claude" / "tools" / "hook_parity_docs.py",
)
assert _DOCS_SPEC and _DOCS_SPEC.loader
hook_parity_docs = importlib.util.module_from_spec(_DOCS_SPEC)
_DOCS_SPEC.loader.exec_module(hook_parity_docs)


def _args(**kwargs) -> argparse.Namespace:
    defaults = {"truncate": True, "compact": True, "caveman": True}
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def test_manifest_has_one_spec_per_hook_name():
    names = [spec.name for spec in HOOK_SPECS]
    assert len(names) == len(set(names))


def test_parity_matrix_matches_manifest():
    """PT3/ESR3: parity.json must distinguish source-registration (verifiable
    against HOOK_SPECS, below) from installed-and-active state (checkout-specific,
    never asserted here as a bare boolean — only the live checker that can verify
    it, or "none"/"n/a" when no such checker exists yet)."""
    parity = json.loads(
        (REPO / "agents" / "common" / "hooks" / "parity.json").read_text()
    )
    manifest_names = {spec.name for spec in HOOK_SPECS}
    assert set(parity) == manifest_names
    for spec in HOOK_SPECS:
        claude_source = "shipped" if spec.claude else "missing"
        codex_source = "shipped" if spec.codex else "missing"
        claude_row = parity[spec.name]["claude"]
        codex_row = parity[spec.name]["codex"]
        assert claude_row["source"] == claude_source
        assert codex_row["source"] == codex_source
        # "installed_check" names the live mechanism that verifies wiring in a
        # given checkout, or "n/a" when no source exists to install, or "none"
        # when source exists but no per-hook live checker has shipped yet.
        assert claude_row["installed_check"] == ("none" if spec.claude else "n/a")
        assert codex_row["installed_check"] == (
            "codex_parity_audit.py" if spec.codex else "n/a"
        )
        if spec.optional_flag:
            assert parity[spec.name].get("optional") is True


def test_emitters_are_generated_from_manifest(tmp_path):
    args = _args()
    claude = build_claude_hook_entries(
        tmp_path / ".venv" / "bin" / "python", tmp_path, args
    )
    codex = build_codex_hook_entries(
        tmp_path / ".venv" / "bin" / "python", tmp_path, args
    )
    expected_claude = sum(len(spec.claude) for spec in HOOK_SPECS)
    expected_codex = sum(len(spec.codex) for spec in HOOK_SPECS)
    assert len(claude) == expected_claude
    assert len(codex) == expected_codex
    assert any("caveman-reminder.py" in cmd for _, _, cmd in claude)
    assert any("terse-reminder.py" in cmd for _, _, cmd in codex)


def test_hook_parity_docs_render_from_manifest():
    block = hook_parity_docs.render()
    assert "Feature parity means" in block
    assert "Enforcement parity is intentionally different" in block
    assert "`search-first`" in block
    assert ".claude/hooks/search-first.py" in block
    assert ".codex/hooks/search-first.py" in block
    assert "best-effort" in block


def test_hook_parity_docs_are_current():
    block = hook_parity_docs.render()
    for path in hook_parity_docs.DOCS:
        text = path.read_text(encoding="utf-8")
        assert hook_parity_docs._replace_block(text, block) == text


def test_codex_hooks_json_value_is_event_keyed():
    flat = [
        {"event": "PreToolUse", "matcher": "Bash", "command": "pre.py"},
        {"event": "PostToolUse", "matcher": "Bash", "command": "post.py"},
        {"event": "PostToolUse", "matcher": "Edit", "command": "post2.py"},
    ]
    rendered = codex_hooks_json_value(flat)
    assert set(rendered) == {"PreToolUse", "PostToolUse"}
    assert len(rendered["PreToolUse"]) == 1
    assert len(rendered["PostToolUse"]) == 2
    assert all("event" not in group for groups in rendered.values() for group in groups)


def test_codex_hooks_json_value_round_trips_through_flatten():
    flat = [
        {"event": "PreToolUse", "matcher": "Bash", "command": "pre.py"},
        {"event": "PostToolUse", "matcher": "Bash", "command": "post.py"},
    ]
    reflattened, well_formed = flatten_codex_hooks(codex_hooks_json_value(flat))
    assert well_formed
    assert sorted(reflattened, key=lambda h: h["command"]) == sorted(
        flat, key=lambda h: h["command"]
    )


def test_codex_hooks_json_value_empty_is_empty():
    assert codex_hooks_json_value([]) == {}


def test_codex_hooks_legacy_nested_input_migrates_to_event_keyed():
    legacy = [
        [
            {
                "event": "PreToolUse",
                "matcher": "Bash",
                "hooks": [{"type": "command", "command": "pre.py"}],
            }
        ]
    ]
    flat, well_formed = flatten_codex_hooks(legacy)
    assert well_formed
    assert codex_hooks_schema(legacy) == "legacy-nested"
    rendered = codex_hooks_json_value(flat)
    assert codex_hooks_schema(rendered) == "event-keyed"
    assert rendered["PreToolUse"][0]["hooks"][0]["command"] == "pre.py"


def test_codex_hooks_preserve_unrelated_valid_metadata():
    current = {
        "Stop": [
            {
                "statusMessage": "Checking",
                "hooks": [
                    {
                        "type": "command",
                        "command": "user.py",
                        "timeout": 12,
                    }
                ],
            }
        ],
    }
    flat, well_formed = flatten_codex_hooks(current)
    assert well_formed
    assert codex_hooks_json_value(flat) == current


def test_codex_hook_release_window_is_explicit():
    assert CODEX_HOOK_CONTRACT_RANGE == "0.142.3–0.145.0"
    assert parse_codex_version("codex-cli 0.142.3") == (0, 142, 3)
    assert codex_hook_contract_supports((0, 142, 3))
    assert codex_hook_contract_supports((0, 145, 0))
    assert not codex_hook_contract_supports((0, 142, 2))
    assert not codex_hook_contract_supports((0, 145, 1))
