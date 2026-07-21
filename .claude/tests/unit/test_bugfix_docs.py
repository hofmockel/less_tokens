"""Unit tests for tools/bugfix_docs.py — bugfix-protocol.md block renderer."""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]


def _load(name: str, rel_path: str):
    spec = importlib.util.spec_from_file_location(name, REPO / rel_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


docs = _load("bugfix_docs", ".claude/tools/bugfix_docs.py")


def test_check_passes_clean_against_shipped_protocol():
    assert docs.update_docs(check=True) == 0


def test_all_rendered_blocks_present_in_shipped_protocol():
    protocol_text = docs.PROTOCOL.read_text(encoding="utf-8")
    for name, render in docs.RENDERERS.items():
        assert render() in protocol_text, f"{name} block out of sync"


def test_replace_block_raises_without_markers():
    import pytest

    with pytest.raises(ValueError):
        docs._replace_block("no markers here", "severity-rubric", "replacement")


def test_verification_commands_render_includes_all_registry_commands():
    rendered = docs._render_verification_commands()
    for vc in docs.VERIFICATION_COMMANDS:
        assert vc.command in rendered
        assert vc.label in rendered


def test_mode_detection_block_matches_bug_hunt_docs_verbatim():
    """bug-hunt-protocol.md and bugfix-protocol.md must share the exact same
    mode-detection text — that's the whole point of sourcing both from
    protocol_mode.py instead of hand-copying prose into each doc."""
    bug_hunt_docs = _load("bug_hunt_docs", ".claude/tools/bug_hunt_docs.py")
    assert docs._render_mode_detection() == bug_hunt_docs._render_mode_detection()


def test_severity_tiers_reused_from_bug_hunt_registry():
    # Import (not _load) so this hits the same sys.modules-cached bug_hunt_registry
    # that `docs` already imported transitively via bugfix_registry — re-exec'ing a
    # fresh copy via _load would define a structurally-identical but distinct
    # SeverityTier class, and dataclass equality checks class identity too.
    import bug_hunt_registry  # noqa: E402  (available: docs's load put tools/ on sys.path)

    assert docs.SEVERITY_TIERS == bug_hunt_registry.SEVERITY_TIERS
    assert docs.SEVERITY_TIERS is bug_hunt_registry.SEVERITY_TIERS
