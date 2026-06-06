"""Parity tests: is_indexed() must behave identically in search-first.py and index-refresh.py.

The known divergence (mid-path excluded dir) is documented as an xfail so the
test suite turns green when the bug is fixed without extra ceremony.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import REPO_ROOT, load_hook


@pytest.fixture(scope="module")
def search_first(tmp_path_factory):
    """Load hooks/search-first.py and patch REPO + _config for isolated testing."""
    tmp = tmp_path_factory.mktemp("sf_repo")
    mod = load_hook(REPO_ROOT / ".claude" / "hooks" / "search-first.py")
    mod.REPO = tmp
    mod._config["excluded_names"] = {"legacy"}
    mod._config["excluded_prefixes"] = ("legacy/",)
    mod._config["dirs"] = ("tools/",)
    mod._config["root_globs"] = ("*.md",)
    return mod, tmp


@pytest.fixture(scope="module")
def index_refresh(tmp_path_factory):
    """Load hooks/index-refresh.py and patch REPO + globals for isolated testing."""
    tmp = tmp_path_factory.mktemp("ir_repo")
    mod = load_hook(REPO_ROOT / ".claude" / "hooks" / "index-refresh.py")
    mod.REPO = tmp
    mod.EXCLUDED_DIR_NAMES = {"legacy"}
    mod.EXCLUDED_DIR_PREFIXES = ("legacy/",)
    mod.INDEXED_DIRS = ("tools/",)
    return mod, tmp


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def sf_indexed(mod_pair, rel: str) -> bool:
    mod, repo = mod_pair
    return mod.is_indexed(repo / rel)


def ir_indexed(mod_pair, rel: str) -> bool:
    mod, repo = mod_pair
    return mod.is_indexed(repo / rel)


# ---------------------------------------------------------------------------
# Cases where both hooks must agree
# ---------------------------------------------------------------------------

class TestParity:
    def test_indexed_python_file(self, search_first, index_refresh):
        assert sf_indexed(search_first, "tools/foo.py") == ir_indexed(index_refresh, "tools/foo.py")
        assert sf_indexed(search_first, "tools/foo.py") is True

    def test_indexed_sql_file(self, search_first, index_refresh):
        assert sf_indexed(search_first, "tools/schema.sql") == ir_indexed(index_refresh, "tools/schema.sql")
        assert sf_indexed(search_first, "tools/schema.sql") is True

    def test_root_md_file(self, search_first, index_refresh):
        assert sf_indexed(search_first, "README.md") == ir_indexed(index_refresh, "README.md")
        assert sf_indexed(search_first, "README.md") is True

    def test_non_indexed_directory(self, search_first, index_refresh):
        assert sf_indexed(search_first, "other/foo.py") == ir_indexed(index_refresh, "other/foo.py")
        assert sf_indexed(search_first, "other/foo.py") is False

    def test_md_under_source_dir_not_gated(self, search_first, index_refresh):
        """A .md under an INDEXED_SOURCE_DIRS entry is never collected by
        enumerate_sources() (only *.py / *.sql there), so is_indexed() must
        return False — otherwise the search-first gate is unclearable."""
        assert sf_indexed(search_first, "tools/notes.md") == ir_indexed(index_refresh, "tools/notes.md")
        assert sf_indexed(search_first, "tools/notes.md") is False

    def test_non_indexed_extension(self, search_first, index_refresh):
        assert sf_indexed(search_first, "tools/data.json") == ir_indexed(index_refresh, "tools/data.json")
        assert sf_indexed(search_first, "tools/data.json") is False

    def test_root_level_exclusion(self, search_first, index_refresh):
        """A top-level excluded prefix: legacy/foo.py should be excluded by both."""
        assert sf_indexed(search_first, "legacy/foo.py") == ir_indexed(index_refresh, "legacy/foo.py")
        assert sf_indexed(search_first, "legacy/foo.py") is False

    def test_path_outside_repo(self, search_first, index_refresh):
        mod_sf, _ = search_first
        mod_ir, _ = index_refresh
        outside = Path("/tmp/unrelated.py")
        assert mod_sf.is_indexed(outside) is False
        assert mod_ir.is_indexed(outside) is False


# ---------------------------------------------------------------------------
# Known divergence: mid-path excluded directory
# ---------------------------------------------------------------------------

class TestKnownDivergence:
    def test_midpath_excluded_dir_parity(self, search_first, index_refresh):
        """tools/legacy/foo.py — 'legacy/' is an excluded prefix; both hooks must agree."""
        sf_result = sf_indexed(search_first, "tools/legacy/foo.py")
        ir_result = ir_indexed(index_refresh, "tools/legacy/foo.py")
        assert sf_result == ir_result, (
            f"search-first={sf_result}, index-refresh={ir_result} for tools/legacy/foo.py"
        )
        assert sf_result is False, "mid-path excluded dir should not be indexed"
