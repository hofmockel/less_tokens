"""Guard: the shipped INDEXED_SOURCE_DIRS default must not reintroduce "app/".

The installer never creates an app/ directory, so listing it made fresh
installs report a health gap for every (absent) file under app/. It was
removed; this test keeps the stale default from creeping back, and asserts
CLAUDE.md no longer documents it as a live known bug.
"""
from __future__ import annotations

import sys

from tests.conftest import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "tools"))
import search_config  # noqa: E402


def test_default_source_dirs_excludes_app():
    assert "app/" not in search_config.INDEXED_SOURCE_DIRS
    assert search_config.INDEXED_SOURCE_DIRS == ("tools/", "schema/")


def test_claude_md_known_bugs_drops_stale_app_entry():
    text = (REPO_ROOT / "CLAUDE.md").read_text()
    known = text.split("## Known bugs worth avoiding", 1)[1]
    assert "app/" not in known
