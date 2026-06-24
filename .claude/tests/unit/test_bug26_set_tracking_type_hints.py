"""Bug 26: stats._set_tracking regex fails on complex type hints.

The pattern "(?:\\s*:\\s*\\w+)?" only matches simple single-word type hints
(bool, int, str).  Complex forms like 'bool | None' or 'Optional[bool]'
caused the regex to fail to match, leaving TRACK_SAVINGS unchanged with no
error.  The fix broadens the type-hint capture to [^=]+ so any annotation
that does not contain '=' is accepted.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / ".claude" / "tools"))


def _import_stats():
    import stats
    return importlib.reload(stats)


_COMPLEX_HINTS = [
    ("TRACK_SAVINGS: bool | None = False\n", "bool | None"),
    ("TRACK_SAVINGS: Optional[bool] = False\n", "Optional[bool]"),
    ("TRACK_SAVINGS:bool|None=False\n", "bool|None"),
]


def test_set_tracking_handles_complex_type_hints(tmp_path):
    """_set_tracking must succeed when TRACK_SAVINGS has a complex type hint."""
    stats = _import_stats()
    for src, hint_desc in _COMPLEX_HINTS:
        safe = hint_desc.replace(' ', '_').replace('[', '').replace(']', '').replace('|', '_or_')
        cfg = tmp_path / f"cfg_{safe}.py"
        cfg.write_text(src)
        with patch("stats.CONFIG_FILE", cfg):
            stats._set_tracking(True)
        result = cfg.read_text()
        assert "True" in result and "False" not in result, (
            f"_set_tracking failed for type hint '{hint_desc}'; "
            f"file unchanged: {result!r}"
        )
