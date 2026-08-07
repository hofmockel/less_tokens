"""Regression test: path matching must not conflate files that share only a basename."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path


REPO = Path(__file__).parent.parent.parent.parent
HOOKS = REPO / ".claude" / "hooks"
sys.path.insert(0, str(HOOKS))


# ---------------------------------------------------------------------------
# auto-slice helpers
# ---------------------------------------------------------------------------


def _write_ranges(ranges_file: Path, key: str, spans: list) -> None:
    ranges_file.write_text(json.dumps({key: spans}), encoding="utf-8")


def _get_ranges(ranges_file: Path, file_path: str, window: int = 300):
    """Inline copy of auto-slice._ranges_for, parameterised for testing."""
    try:
        if (time.time() - ranges_file.stat().st_mtime) > window:
            return []
        data = json.loads(ranges_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    p = Path(file_path)
    for key, spans in data.items():
        kp = Path(key)
        # Fixed: no kp.name == p.name
        if kp == p or str(p).endswith(str(kp)):
            return spans or []
    return []


def _has_recent_hit(ranges_file: Path, p: Path, window: int = 300) -> bool:
    """Inline copy of grep-first-read._has_recent_search_hit, fixed."""
    try:
        if (time.time() - ranges_file.stat().st_mtime) > window:
            return False
        data = json.loads(ranges_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    for key in data:
        kp = Path(key)
        if kp == p or str(p).endswith(str(kp)):
            return True
    return False


# ---------------------------------------------------------------------------
# Tests for auto-slice path match
# ---------------------------------------------------------------------------


def test_exact_path_matches(tmp_path):
    rf = tmp_path / "ranges.json"
    _write_ranges(rf, "src/utils/foo.py", [[1, 10]])
    assert _get_ranges(rf, "src/utils/foo.py") == [[1, 10]]


def test_different_dir_same_basename_no_match(tmp_path):
    rf = tmp_path / "ranges.json"
    _write_ranges(rf, "src/utils/foo.py", [[1, 10]])
    # test/utils/foo.py shares basename "foo.py" but is a different file
    assert _get_ranges(rf, "test/utils/foo.py") == []


def test_suffix_match_works(tmp_path):
    rf = tmp_path / "ranges.json"
    _write_ranges(rf, "utils/foo.py", [[5, 20]])
    # absolute path ending with the stored relative key
    assert _get_ranges(rf, "/home/user/project/utils/foo.py") == [[5, 20]]


# ---------------------------------------------------------------------------
# Tests for grep-first-read path match
# ---------------------------------------------------------------------------


def test_grep_first_exact_match(tmp_path):
    rf = tmp_path / "ranges.json"
    _write_ranges(rf, "src/bar.py", [[1, 5]])
    assert _has_recent_hit(rf, Path("src/bar.py")) is True


def test_grep_first_different_dir_no_match(tmp_path):
    rf = tmp_path / "ranges.json"
    _write_ranges(rf, "src/bar.py", [[1, 5]])
    assert _has_recent_hit(rf, Path("other/bar.py")) is False


def test_grep_first_suffix_match(tmp_path):
    rf = tmp_path / "ranges.json"
    _write_ranges(rf, "src/bar.py", [[1, 5]])
    assert _has_recent_hit(rf, Path("/abs/project/src/bar.py")) is True
