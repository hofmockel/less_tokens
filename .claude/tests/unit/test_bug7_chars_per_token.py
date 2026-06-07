"""Bug 7: token warning uses magic number 4 instead of a named constant.

search.py warned about large result sets using `// 4` hardcoded, making the
chars-per-token ratio invisible and non-configurable.  The fix moves it to
`search_config.CHARS_PER_TOKEN` so users can tune it alongside other config.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / ".claude" / "tools"))


def test_chars_per_token_constant_exists():
    """search_config must expose CHARS_PER_TOKEN (was hardcoded magic 4)."""
    import search_config

    assert hasattr(search_config, "CHARS_PER_TOKEN"), (
        "search_config.CHARS_PER_TOKEN missing — add it so the token heuristic "
        "is configurable (Bug 7)"
    )
    assert isinstance(search_config.CHARS_PER_TOKEN, int)
    assert search_config.CHARS_PER_TOKEN > 0


def test_search_uses_chars_per_token_not_magic_four():
    """search.py must reference CHARS_PER_TOKEN, not hardcode // 4 in the warning."""
    src = (REPO / ".claude" / "tools" / "search.py").read_text()
    assert "CHARS_PER_TOKEN" in src, (
        "search.py still uses hardcoded // 4 for token estimate; "
        "replace with search_config.CHARS_PER_TOKEN (Bug 7)"
    )
