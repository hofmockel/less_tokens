"""Bug 20: search-first.py had a hardcoded 300 fallback in search_was_recent().

`_config.get("window_seconds", 300)` silently used 300 when the config key was
absent, bypassing the value in search_config.py and masking config-load
failures.  Since search_was_recent() is only called after _load_config()
succeeds (which always sets window_seconds), the fallback was unreachable in
normal operation but hid bugs in tests and edge cases.

The fix removes the magic fallback: access _config["window_seconds"] directly
so a missing key raises KeyError (logic bug) rather than silently using 300.
"""

from __future__ import annotations

import sys

from tests.conftest import REPO_ROOT, load_hook

sys.path.insert(0, str(REPO_ROOT / ".claude" / "tools"))


def test_no_hardcoded_300_fallback_in_search_was_recent():
    """search-first.py must not use a hardcoded 300 as fallback for window_seconds."""
    src = (REPO_ROOT / ".claude" / "hooks" / "search-first.py").read_text()
    # The literal 300 must not appear as a .get() fallback for window_seconds.
    assert '_config.get("window_seconds", 300)' not in src, (
        "search-first.py still uses hardcoded 300 as fallback for window_seconds (Bug 20)"
    )


def test_search_was_recent_uses_config_window(tmp_path):
    """search_was_recent() must respect window_seconds from _config, not a fallback."""
    mod = load_hook(REPO_ROOT / ".claude" / "hooks" / "search-first.py")
    state_file = tmp_path / "last-search"
    state_file.write_text("q")

    # Write the state file, then call search_was_recent with a short window.
    # A 1-second window should always see a just-written file as recent.
    mod._config.clear()
    mod._config["window_seconds"] = 1
    mod._config["state_file"] = state_file
    assert mod.search_was_recent() is True

    # A 0-second window should never see ANY file as recent.
    mod._config["window_seconds"] = 0
    assert mod.search_was_recent() is False
