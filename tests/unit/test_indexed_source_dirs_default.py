"""Guard: INDEXED_SOURCE_DIRS default must be empty (tools/schema live in .claude/).

The installer deploys tools/ and schema/ into .claude/tools/ and .claude/schema/,
so listing them in the default would cause healthy installs to report coverage
gaps. The default is () so the installer's auto-discover step fills it per host.
"""
from __future__ import annotations

import sys

from tests.conftest import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "tools"))
import search_config  # noqa: E402


def test_default_source_dirs_is_empty():
    assert search_config.INDEXED_SOURCE_DIRS == ()


def test_claude_md_known_bugs_drops_stale_app_entry():
    text = (REPO_ROOT / "CLAUDE.md").read_text()
    known = text.split("## Known bugs worth avoiding", 1)[1]
    assert "app/" not in known
