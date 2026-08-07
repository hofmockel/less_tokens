"""Installer can wire hooks into settings.local.json with --local.

By default, install.py writes the project-shared `.claude/settings.json`
(stable against Claude's permission rewrites). `--local` opts into
`settings.local.json` for solo / personal installs. Also: when the
default target is a pre-existing non-empty `settings.json`, print a
one-line notice that a committed file is being modified.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))


def test_local_flag_is_exposed():
    src = (REPO / "install.py").read_text()
    assert "--local" in src
    assert "settings.local.json" in src


def test_main_routes_settings_path_via_args_local():
    """The settings_path assignment in main() must consider `args.local`,
    not be a fixed `.claude/settings.json` constant."""
    src = (REPO / "install.py").read_text()
    # We expect a conditional involving args.local before the wire_settings
    # call. The simplest evidence: the source contains both a settings.json
    # path and a settings.local.json path, gated on args.local.
    assert "args.local" in src
    assert '"settings.local.json"' in src or "'settings.local.json'" in src
