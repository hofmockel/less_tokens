"""Installer builds the index by default; --no-build opts out.

A default install previously left no index.db, so tools/search.py
returned empty until the user ran the build manually. Making build
default-on completes the install in one pass; --no-build is the escape
hatch for users who want to defer the model download.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))


def test_no_build_flag_is_exposed():
    src = (REPO / "install.py").read_text()
    assert "--no-build" in src


def test_main_uses_inverted_build_default():
    """Call site should derive build intent from `not args.no_build`
    (or equivalent) rather than checking the old opt-in `args.build`."""
    src = (REPO / "install.py").read_text()
    assert "args.no_build" in src
    # The old opt-in `args.build` should be gone (would mean we forgot
    # a call site).
    assert "args.build" not in src.replace("args.no_build", "")
