"""WINDOW_SECONDS lives in search_config.py, not hardcoded in the hook.

Users tune the search-gate window without editing hook source.
"""

from __future__ import annotations

from tests.conftest import REPO_ROOT, load_hook


def test_window_seconds_in_search_config():
    import search_config

    assert hasattr(search_config, "WINDOW_SECONDS")
    assert isinstance(search_config.WINDOW_SECONDS, int)
    assert search_config.WINDOW_SECONDS > 0


def test_hook_reads_window_from_config(monkeypatch):
    import search_config

    monkeypatch.setattr(search_config, "WINDOW_SECONDS", 999)
    mod = load_hook(REPO_ROOT / ".claude" / "hooks" / "search-first.py")
    # Force config reload so the patched value is picked up.
    mod._config.clear()
    assert mod._load_config()
    assert mod._config["window_seconds"] == 999


def test_hook_source_has_no_hardcoded_window():
    src = (REPO_ROOT / ".claude" / "hooks" / "search-first.py").read_text()
    # The literal must not appear as an assignment in the hook.
    assert "WINDOW_SECONDS = 300" not in src
