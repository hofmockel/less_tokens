"""Bug: _locate_range returns wrong range on duplicate first line.

When the last-line confirmation fails, the function immediately returns a
fallback range for the wrong occurrence instead of continuing the loop to find
the correct one.

Fix: save the fallback but continue the loop; return the first fallback only
after exhausting all candidates.
"""
from __future__ import annotations

import sys

from tests.conftest import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / ".claude" / "tools"))
from search import _locate_range  # noqa: E402


def test_duplicate_first_line_returns_correct_occurrence():
    """_locate_range must find the occurrence whose last line also matches."""
    # File with two occurrences of the same first line; only the second has
    # the right last line.
    file_text = "\n".join([
        "def foo():",       # line 1  — first occurrence, wrong last line
        "    return 1",     # line 2
        "def foo():",       # line 3  — second occurrence, correct last line
        "    return 42",    # line 4
    ])
    chunk_text = "\n".join([
        "def foo():",
        "    return 42",
    ])

    result = _locate_range(file_text, chunk_text)

    assert result is not None, "_locate_range must find the chunk"
    start, end = result
    assert start == 3, f"expected start=3 (second occurrence), got {start}"
    assert end == 4, f"expected end=4, got {end}"


def test_no_matching_last_line_returns_first_fallback():
    """When no occurrence has a matching last line, return the first occurrence."""
    file_text = "\n".join([
        "def foo():",   # line 1
        "    pass",     # line 2
        "def foo():",   # line 3
        "    pass",     # line 4
    ])
    # Chunk whose last line doesn't appear at the expected offset in either occurrence
    chunk_text = "\n".join([
        "def foo():",
        "    return 99",  # doesn't exist in file
    ])

    result = _locate_range(file_text, chunk_text)

    # Should fall back to the first occurrence, not crash
    assert result is not None
    start, end = result
    assert start == 1, f"expected fallback to first occurrence (line 1), got {start}"
