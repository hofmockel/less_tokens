"""Regression: search-first.py docstring must name the settings file the
installer actually writes.

install.py wires hooks into the project-shared .claude/settings.json (not
settings.local.json) so Claude rewrites can't clobber them. The hook docstring
previously said settings.local.json, misleading anyone debugging why the gate
isn't firing.
"""
from __future__ import annotations

from tests.conftest import REPO_ROOT, load_hook


def test_docstring_names_settings_json_not_local():
    mod = load_hook(REPO_ROOT / "hooks" / "search-first.py")
    doc = mod.__doc__ or ""
    assert "settings.local.json" not in doc
    assert "settings.json" in doc
