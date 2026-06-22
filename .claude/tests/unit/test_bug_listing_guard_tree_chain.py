"""Bug: listing-guard tree detection uses re.match (start-anchored).

`echo foo && tree` bypasses the guard because re.match only tests from the
start of the string. The ls guard correctly uses re.search. The fix is to
replace re.match with re.search for the tree check.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_repo = Path(__file__).parent.parent.parent.parent
_hook = _repo / ".claude" / "hooks" / "listing-guard.py"
_common = str(_repo / "agents" / "common" / "hooks")
if _common not in sys.path:
    sys.path.insert(0, _common)
_spec = importlib.util.spec_from_file_location("_listing_guard_hook", _hook)
_mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]
is_bare_listing = _mod.is_bare_listing


def test_tree_after_chain_is_intercepted():
    """`echo foo && tree` should be intercepted (tree present, no -L)."""
    intercepted, _ = is_bare_listing("echo foo && tree")
    assert intercepted, (
        "listing-guard missed tree in chained command (re.match bug)"
    )


def test_tree_with_semicolon_chain_is_intercepted():
    """`cd /tmp; tree` should be intercepted."""
    intercepted, _ = is_bare_listing("cd /tmp; tree")
    assert intercepted, (
        "listing-guard missed tree in semicolon-chained command"
    )


def test_plain_tree_still_intercepted():
    """Bare `tree` must still be intercepted (regression guard)."""
    intercepted, _ = is_bare_listing("tree")
    assert intercepted


def test_tree_with_safe_depth_not_intercepted():
    """`tree -L 2` must not be intercepted (regression guard)."""
    intercepted, _ = is_bare_listing("tree -L 2")
    assert not intercepted


def test_word_tree_in_argument_not_intercepted():
    """`git commit -m "tree detection fix"` must not be intercepted."""
    intercepted, _ = is_bare_listing('git commit -m "tree detection fix"')
    assert not intercepted, (
        "listing-guard false-positive: 'tree' in argument flagged as tree command"
    )
