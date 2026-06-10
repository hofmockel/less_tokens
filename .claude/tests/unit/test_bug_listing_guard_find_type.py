"""Bug: listing-guard false-positive on `find . -type f`.

`-type` is absent from _ALLOW_RE, so `find . -type f` is intercepted as a
bare dump. The fix is to add `type` to the allowed predicates list.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_hook = Path(__file__).parent.parent.parent / "hooks" / "listing-guard.py"
_spec = importlib.util.spec_from_file_location("listing_guard", _hook)
_mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["listing_guard"] = _mod
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]
is_bare_listing = _mod.is_bare_listing


def test_find_type_f_not_intercepted():
    """`find . -type f` must not be intercepted — it is a selective predicate."""
    intercepted, _ = is_bare_listing("find . -type f")
    assert not intercepted, (
        "listing-guard false-positive: `find . -type f` intercepted as bare dump"
    )


def test_find_type_d_not_intercepted():
    """`find . -type d` must not be intercepted."""
    intercepted, _ = is_bare_listing("find . -type d")
    assert not intercepted


def test_bare_find_still_intercepted():
    """`find .` without predicates must still be intercepted (regression guard)."""
    intercepted, _ = is_bare_listing("find .")
    assert intercepted


def test_find_name_still_allowed():
    """`find . -name '*.py'` must not be intercepted (regression guard)."""
    intercepted, _ = is_bare_listing("find . -name '*.py'")
    assert not intercepted
