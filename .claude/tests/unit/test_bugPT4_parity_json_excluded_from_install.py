"""Regression test for PT4: parity.json is a canonical-only tracking file that
nothing downstream reads from an installed copy (hook_parity_docs.py,
test_hook_manifest_parity.py, and codex_parity_audit.py all read the source
tree's agents/common/hooks/parity.json or compare against .codex/ directly),
so copy_tree must not distribute it to .claude/hooks/common or .less_tokens/hooks."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(REPO))
from install import _install_specs


def _exclude_for(specs, dest: str) -> frozenset[str]:
    matches = [s for s in specs if s[1] == dest]
    assert matches, f"no install spec targets {dest!r}"
    return matches[0][2]


def test_claude_common_hooks_excludes_parity_json():
    specs = _install_specs(caveman=False, agents={"claude"})
    assert "parity.json" in _exclude_for(specs, ".claude/hooks/common")


def test_codex_less_tokens_hooks_excludes_parity_json():
    specs = _install_specs(caveman=False, agents={"codex"})
    assert "parity.json" in _exclude_for(specs, ".less_tokens/hooks")
