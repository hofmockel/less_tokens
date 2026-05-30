"""NEXT STEPS output warns that the search-first gate is now active.

Wiring the PreToolUse hook immediately changes Read behavior for any
already-running Claude session in the target - reads of indexed files
error until a search runs within the gate window. Surfacing this in the
install summary saves the user a confused debugging trip.
"""
from __future__ import annotations

from tests.conftest import REPO_ROOT


def test_install_next_steps_mentions_search_first_gate():
    src = (REPO_ROOT / "install.py").read_text()
    # The notice must reference the gate and the WINDOW_SECONDS knob so a
    # surprised user finds the right config to tune.
    assert "search-first" in src.lower()
    assert "WINDOW_SECONDS" in src
    # Must call out the active-session behavior change (the key surprise).
    assert "already-running" in src or "restart" in src.lower() or "active session" in src.lower()
